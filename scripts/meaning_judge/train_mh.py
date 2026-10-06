"""Four-head meaning verifier: an LLM body (LoRA) + a 4-output linear head on the last hidden state.

Heads: same / added / missing / contradict, each a sigmoid score in 0-1. The input is the benchmark prompt for the
"same" question; head "same" is initialised to the LM's (Yes - No) unembedding direction, the other three to its
negative, so training starts from the zero-shot judge instead of a random head. Combined score (the reward):
min(same, 1 - added, 1 - missing, 1 - contradict).

Labels per row:
  judged rows (teacher_*)  blend * Gemma 4 31B + (1 - blend) * Jev, per question
  planted / targeted rows  certain 0/1 per question (see ORIGIN_KIND)

  python train_mh.py --model google/gemma-4-E2B-it --init-adapter runs/e2b_ep2/adapter --out runs/e2b_mh
  python train_mh.py ... --n-train 512 --steps 10 --eval-every 10       # smoke test
Writes runs/<out>/{adapter,heads.pt}, llm_ft_<out>.jsonl (bench: same/added/missing/contradict) + .meta.json.
"""
import argparse, json, math, random, sys, time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS
from paths import BENCH, BENCH_DIR, VERIFIER_DATA, load_split

SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
       "difficulty. Answer with a single word: Yes or No.")
HEADS = ("same", "added", "missing", "contradict")
JEV_KEY = {"same": "y", "added": "adds", "missing": "drops", "contradict": "changes"}
ORIGIN_KIND = {"pos_samer": "same", "pos_aug": "same", "pos_split": "same", "pos_resplit": "same",
               "neg_addition": "added",
               "neg_hedge_drop": "missing", "neg_clause_drop": "missing", "neg_span_drop": "missing", "neg_adj_drop": "missing",
               "neg_negation": "contradict", "neg_number": "contradict", "neg_quantifier": "contradict",
               "neg_connector": "contradict", "neg_antonym": "contradict", "neg_question": "contradict"}

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--init-adapter", default=None)
ap.add_argument("--data", default=str(VERIFIER_DATA))
ap.add_argument("--targeted", default=str(BENCH_DIR / "data_mh"))
ap.add_argument("--gemma-same", default=str(BENCH_DIR / "teacher_gemma31b.jsonl"))
ap.add_argument("--gemma-mq", default=str(BENCH_DIR / "teacher_gemma31b_mq.jsonl"))
ap.add_argument("--blend", type=float, default=0.85)
ap.add_argument("--n-train", type=int, default=60000)
ap.add_argument("--n-val", type=int, default=2000)
ap.add_argument("--bs", type=int, default=16)
ap.add_argument("--accum", type=int, default=2)
ap.add_argument("--lr", type=float, default=5e-5)
ap.add_argument("--head-lr", type=float, default=1e-3)
ap.add_argument("--r", type=int, default=16)
ap.add_argument("--max-len", type=int, default=512)
ap.add_argument("--eval-every", type=int, default=400)
ap.add_argument("--steps", type=int, default=0)
ap.add_argument("--seed", type=int, default=15)
ap.add_argument("--data-seed", type=int, default=13)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
log = lambda *x: print(f"[{time.time() - t0:6.0f}s]", *x, flush=True)
read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]

# ------------------------------------------------------------------ data ----
D = Path(a.data)
jl = {r["key"]: r for r in read(D / "jev_labels.jsonl")}
gs = {r["key"]: r["p"] for r in read(a.gemma_same)}
gm = {r["key"]: r for r in read(a.gemma_mq)} if Path(a.gemma_mq).exists() else {}
if not gm and not a.steps:
    sys.exit(f"missing {a.gemma_mq} (only a --steps smoke test may run without it)")

def labels(r):
    if "labels" in r:
        return [r["labels"][h] for h in HEADS]
    o = r["origin"]
    if o in ORIGIN_KIND:
        return [1.0 if h == ORIGIN_KIND[o] else 0.0 for h in HEADS]
    if r["key"] not in gm:   # smoke test before the 3-question labels exist: Jev stands in
        return [float(jl[r["key"]][JEV_KEY[h]]) for h in HEADS]
    g = {"same": gs[r["key"]], **{h: gm[r["key"]][h] for h in HEADS[1:]}}
    return [a.blend * g[h] + (1 - a.blend) * float(jl[r["key"]][JEV_KEY[h]]) for h in HEADS]

random.seed(a.data_seed)                      # identical base subsample to train_llm_verifier.py
train = load_split("train", D); val = load_split("val", D)
synth = [r for r in train if not r["origin"].startswith("teacher")]
teach = [r for r in train if r["origin"].startswith("teacher")]
random.shuffle(teach)
train = synth + teach[:max(0, a.n_train - len(synth))] if a.n_train < len(train) else train
random.shuffle(val); val = val[:a.n_val]
tt = read(Path(a.targeted) / "targeted_train.jsonl"); tv = read(Path(a.targeted) / "targeted_val.jsonl")
if a.steps:   # smoke test: keep it small
    train, val, tt, tv = train[:a.n_train], val[:128], tt[:256], tv[:64]
if gm and not a.steps:   # keep only judged rows that have the 3-question teacher labels (labelling may be capped)
    n0 = len(train); train = [r for r in train if not r["origin"].startswith("teacher") or r["key"] in gm]
    v0 = len(val); val = [r for r in val if not r["origin"].startswith("teacher") or r["key"] in gm]
    print(f"judged rows without 3-question labels dropped: train {n0 - len(train)}, val {v0 - len(val)}", flush=True)
train += tt; val += tv
random.seed(a.seed)
log(f"train {len(train)} (targeted {len(tt)}), val {len(val)} (targeted {len(tv)})")

tok = AutoTokenizer.from_pretrained(a.model)
def prompt(src, tgt):
    user = f"Original:\n{src}\n\nRewrite:\n{tgt}\n\nQuestion: {QUESTIONS['same']}\nAnswer Yes or No."
    msg = [{"role": "system", "content": SYS}, {"role": "user", "content": user}]
    try:
        return tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except Exception:
        return tok.apply_chat_template([{"role": "user", "content": SYS + "\n\n" + user}], tokenize=False,
                                       add_generation_prompt=True)
YES = tok.encode("Yes", add_special_tokens=False)[0]; NO = tok.encode("No", add_special_tokens=False)[0]

def encode(rows, with_label=True):
    items = []
    for r in rows:
        ids = tok(prompt(r["src"], r["tgt"]), add_special_tokens=False)["input_ids"]
        if len(ids) > a.max_len:
            continue
        items.append((ids, labels(r) if with_label else [0.0] * 4, r.get("origin", "")))
    return items
tr_items, va_items = encode(train), encode(val)
log(f"encoded: train {len(tr_items)} val {len(va_items)}")

def batches(items, bs, shuffle):
    idx = list(range(len(items)))
    if shuffle:
        random.shuffle(idx)
        chunks = [sorted(idx[k:k + bs * 50], key=lambda i: len(items[i][0])) for k in range(0, len(idx), bs * 50)]
        bl = [c[k:k + bs] for c in chunks for k in range(0, len(c), bs)]
        random.shuffle(bl)
    else:
        idx.sort(key=lambda i: len(items[i][0])); bl = [idx[k:k + bs] for k in range(0, len(idx), bs)]
    for b in bl:
        L = max(len(items[i][0]) for i in b)
        ids = torch.full((len(b), L), tok.pad_token_id); att = torch.zeros((len(b), L), dtype=torch.long)
        for j, i in enumerate(b):
            s = items[i][0]; ids[j, L - len(s):] = torch.tensor(s); att[j, L - len(s):] = 1
        yield b, ids, att, torch.tensor([items[i][1] for i in b], dtype=torch.float32)

# ----------------------------------------------------------------- model ----
from peft import LoraConfig, PeftModel, get_peft_model
model = AutoModelForCausalLM.from_pretrained(a.model, dtype=torch.bfloat16, device_map={"": 0})
model.config.use_cache = False
W = model.get_output_embeddings().weight.detach().float()
d = (W[YES] - W[NO])
if a.init_adapter:
    model = PeftModel.from_pretrained(model, a.init_adapter, is_trainable=True); log("body from", a.init_adapter)
else:
    model = get_peft_model(model, LoraConfig(r=a.r, lora_alpha=2 * a.r, lora_dropout=0.05, bias="none",
        target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"))
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
try:
    model.enable_input_require_grads()
except Exception as e:
    log("enable_input_require_grads skipped:", type(e).__name__)
head = torch.nn.Linear(d.numel(), 4).cuda()
with torch.no_grad():
    head.weight.copy_(torch.stack([d, -d, -d, -d])); head.bias.zero_()
log(f"trainable body {sum(p.numel() for p in model.parameters() if p.requires_grad) / 1e6:.1f}M + head {sum(p.numel() for p in head.parameters())}")

def logits4(ids, att):
    ids, att = ids.cuda(), att.cuda()
    pos = (att.cumsum(-1) - 1).clamp(min=0)
    o = model(input_ids=ids, attention_mask=att, position_ids=pos, output_hidden_states=True, logits_to_keep=1)
    h = o.hidden_states[-1][:, -1, :].float()
    return head(h), (o.logits[:, -1, YES] - o.logits[:, -1, NO]).float()

def combine(p):   # p: [N,4] probabilities
    return np.minimum.reduce([p[:, 0], 1 - p[:, 1], 1 - p[:, 2], 1 - p[:, 3]])

def auc(s, y):
    s, y = np.asarray(s), np.asarray(y, bool)
    if y.all() or (~y).all(): return float("nan")
    r = s.argsort().argsort() + 1.0
    return (r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())

@torch.no_grad()
def predict(items):
    model.eval(); head.eval(); res = {}
    for b, ids, att, _ in batches(items, 32, False):
        lg, _ = logits4(ids, att)
        for i, p in zip(b, torch.sigmoid(lg).cpu().numpy()): res[i] = p
    model.train(); head.train(); return np.stack([res[i] for i in range(len(items))])

def evaluate():
    p = predict(va_items); y = np.array([l for _, l, _ in va_items])
    comb = combine(p); clear = (y[:, 0] >= 0.8) | (y[:, 0] <= 0.2)
    per = {h: auc(p[clear, k], y[clear, k] >= 0.5) for k, h in enumerate(HEADS)}
    tgt = np.array([o.startswith(("neg_span", "neg_adj", "neg_question", "pos_split", "pos_resplit")) for _, _, o in va_items])
    return auc(comb[clear], y[clear, 0] >= 0.8), per, auc(comb[tgt], y[tgt, 0] >= 0.5) if tgt.any() else float("nan")

# sanity: the initialised same-head must reproduce the LM's Yes-No margin (up to logit soft-capping)
with torch.no_grad():
    _, ids, att, _ = next(batches(va_items[:8], 8, False))
    lg, m = logits4(ids, att)
    log("init check  head[same]:", [round(x, 2) for x in lg[:, 0].tolist()[:4]], " LM margin:", [round(x, 2) for x in m.tolist()[:4]])

opt = torch.optim.AdamW([{"params": [p for p in model.parameters() if p.requires_grad], "lr": a.lr},
                         {"params": head.parameters(), "lr": a.head_lr}], weight_decay=0.0)
total = math.ceil(len(tr_items) / a.bs / a.accum) if not a.steps else a.steps
sched = get_cosine_schedule_with_warmup(opt, int(0.03 * total), total)
lossf = torch.nn.BCEWithLogitsLoss()
a0, per0, t0v = evaluate()
log(f"start val AUC(combined) {a0:.4f} targeted {t0v:.4f} per-head {{{', '.join(f'{k}: {v:.3f}' for k, v in per0.items())}}}")
best, step, micro, run = a0, 0, 0, []
model.train()
for b, ids, att, ys in batches(tr_items, a.bs, True):
    lg, _ = logits4(ids, att)
    loss = lossf(lg, ys.cuda()) / a.accum
    loss.backward(); run.append(loss.item() * a.accum); micro += 1
    if micro % a.accum: continue
    torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad] + list(head.parameters()), 1.0)
    opt.step(); sched.step(); opt.zero_grad(); step += 1
    if step % 50 == 0:
        log(f"step {step}/{total} loss {np.mean(run[-100:]):.4f} {torch.cuda.max_memory_allocated() / 2**30:.1f}GB")
    if step % a.eval_every == 0 or step == total:
        av, per, tv_ = evaluate()
        log(f"step {step} val AUC {av:.4f} targeted {tv_:.4f} per-head {{{', '.join(f'{k}: {v:.3f}' for k, v in per.items())}}}")
        if av > best:
            best = av; model.save_pretrained(out / "adapter"); torch.save(head.state_dict(), out / "heads.pt"); log("  saved best")
    if step >= total: break
if not (out / "heads.pt").exists():
    model.save_pretrained(out / "adapter"); torch.save(head.state_dict(), out / "heads.pt")
log(f"training done, best val AUC {best:.4f}")

# ------------------------------------------------------- score the bench ----
from peft import set_peft_model_state_dict
from safetensors.torch import load_file
set_peft_model_state_dict(model, load_file(str(out / "adapter" / "adapter_model.safetensors")))
head.load_state_dict(torch.load(out / "heads.pt"))
bench = read(BENCH)
b_items = [(tok(prompt(r["original"], r["candidate"]), add_special_tokens=False)["input_ids"][-4096:], [0.0] * 4, "") for r in bench]
t1 = time.time(); p = predict(b_items); sec = time.time() - t1
name = out.name
with open(BENCH_DIR / f"llm_ft_{name}.jsonl", "w") as f:
    for r, q in zip(bench, p):
        f.write(json.dumps({"id": r["id"], **{h: float(v) for h, v in zip(HEADS, q)}}) + "\n")
json.dump({"model": f"{a.model} + LoRA + 4 heads ({name})", "mode": "llm-ft-mh", "pairs_per_sec": len(bench) / sec,
           "best_val_auc": best, "start_val_auc": a0, "train_rows": len(tr_items), "blend": a.blend, "total_sec": time.time() - t0},
          open(BENCH_DIR / f"llm_ft_{name}.jsonl.meta.json", "w"), indent=1)
log(f"bench scored: {len(bench)} pairs in {sec:.0f}s ({len(bench) / sec:.1f}/s)")
print("EXIT=0", flush=True)
