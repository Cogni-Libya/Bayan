"""LoRA-train a chat LLM as a meaning verifier in scoring mode, then score the bench.

The input is exactly the benchmark prompt for the "same" question (gpu_run.py llm mode); the model is trained
so that logit(Yes) - logit(No) at the first answer position matches the soft label (Jev same_meaning for judged
pairs, 1/0 for SAMER positives / planted negatives), with BCE-with-logits.

  python train_llm_verifier.py --model google/gemma-4-E2B-it --out runs/e2b --n-train 60000
  SMOKE=1 python train_llm_verifier.py ... --n-train 256 --steps 20      # quick check
Writes: runs/<out>/adapter (best by val AUC), log, and llm_<name>.jsonl (bench scores, key "same").
"""
import argparse, json, math, os, random, sys, time
from pathlib import Path

import numpy as np
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, get_cosine_schedule_with_warmup

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS
from paths import BENCH, BENCH_DIR, VERIFIER_DATA, load_split

SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
       "difficulty. Answer with a single word: Yes or No.")

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--data", default=str(VERIFIER_DATA))
ap.add_argument("--n-train", type=int, default=60000)
ap.add_argument("--bs", type=int, default=16)
ap.add_argument("--accum", type=int, default=2)
ap.add_argument("--lr", type=float, default=1e-4)
ap.add_argument("--r", type=int, default=16)
ap.add_argument("--max-len", type=int, default=512)
ap.add_argument("--eval-every", type=int, default=400)
ap.add_argument("--n-val", type=int, default=2000)
ap.add_argument("--steps", type=int, default=0, help="stop after N optimizer steps (smoke test)")
ap.add_argument("--seed", type=int, default=13)
ap.add_argument("--data-seed", type=int, default=13, help="seed for the row subsample (keep 13 to reuse the same rows)")
ap.add_argument("--teacher", default=None, help="jsonl key -> p from label_teacher.py")
ap.add_argument("--blend", type=float, default=0.5, help="label = blend*teacher + (1-blend)*jev for judged rows")
ap.add_argument("--init-adapter", default=None, help="continue training from this LoRA adapter dir")
a = ap.parse_args()
random.seed(a.data_seed); torch.manual_seed(a.seed)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
t0 = time.time()
log = lambda *x: print(f"[{time.time() - t0:6.0f}s]", *x, flush=True)
read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]

# ------------------------------------------------------------------ data ----
D = Path(a.data)
jl = {r["key"]: r["y"] for r in read(D / "jev_labels.jsonl")}
tl = {json.loads(l)["key"]: json.loads(l)["p"] for l in open(a.teacher)} if a.teacher else {}
def label(r):
    if not r["origin"].startswith("teacher"): return float(r["y"])
    if r["key"] in tl: return a.blend * tl[r["key"]] + (1 - a.blend) * jl[r["key"]]
    if a.teacher: raise KeyError(f"no teacher label for {r['key']}")
    return jl[r["key"]]
train = load_split("train", D); val = load_split("val", D)
synth = [r for r in train if not r["origin"].startswith("teacher")]
teach = [r for r in train if r["origin"].startswith("teacher")]
random.shuffle(teach)
train = synth + teach[:max(0, a.n_train - len(synth))] if a.n_train < len(train) else train
random.shuffle(val); val = val[:a.n_val]
log(f"train {len(train)} (synthetic {len(synth)}), val {len(val)}")

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
log("yes/no ids", YES, NO, repr(tok.decode([YES])), repr(tok.decode([NO])))

def encode(rows, with_label=True):
    items = []
    for r in rows:
        ids = tok(prompt(r["src"], r["tgt"]), add_special_tokens=False)["input_ids"]
        if len(ids) > a.max_len:
            continue
        items.append((ids, label(r) if with_label else None))
    return items
tr_items, va_items = encode(train), encode(val)
random.seed(a.seed)   # batch order; the row subsample above used --data-seed
log(f"encoded: train {len(tr_items)} val {len(va_items)}; median tokens {int(np.median([len(i) for i, _ in tr_items]))}")

def batches(items, bs, shuffle):
    idx = list(range(len(items)))
    if shuffle:   # length-bucketed: sort within chunks of 50 batches, then shuffle the batches
        random.shuffle(idx)
        chunks = [sorted(idx[k:k + bs * 50], key=lambda i: len(items[i][0])) for k in range(0, len(idx), bs * 50)]
        bl = [c[k:k + bs] for c in chunks for k in range(0, len(c), bs)]
        random.shuffle(bl)
    else:
        idx.sort(key=lambda i: len(items[i][0])); bl = [idx[k:k + bs] for k in range(0, len(idx), bs)]
    for b in bl:
        L = max(len(items[i][0]) for i in b)
        ids = torch.full((len(b), L), tok.pad_token_id); att = torch.zeros((len(b), L), dtype=torch.long)
        for j, i in enumerate(b):   # left padding: the answer position is always the last one
            s = items[i][0]; ids[j, L - len(s):] = torch.tensor(s); att[j, L - len(s):] = 1
        ys = torch.tensor([items[i][1] if items[i][1] is not None else 0.0 for i in b], dtype=torch.float32)
        yield b, ids, att, ys

# ----------------------------------------------------------------- model ----
from peft import LoraConfig, get_peft_model
model = AutoModelForCausalLM.from_pretrained(a.model, torch_dtype=torch.bfloat16, device_map={"": 0})
model.config.use_cache = False
cfg = LoraConfig(r=a.r, lora_alpha=2 * a.r, lora_dropout=0.05, bias="none",
                 target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
if a.init_adapter:
    from peft import PeftModel
    model = PeftModel.from_pretrained(model, a.init_adapter, is_trainable=True); log("continuing from", a.init_adapter)
else:
    model = get_peft_model(model, cfg)
model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
try:
    model.enable_input_require_grads()
except Exception as e:
    log("enable_input_require_grads skipped:", type(e).__name__)
ntr = sum(p.numel() for p in model.parameters() if p.requires_grad)
log(f"trainable params {ntr / 1e6:.1f}M")

KEEP = {"logits_to_keep": 1}
def margin(ids, att):
    global KEEP
    ids, att = ids.cuda(), att.cuda()
    pos = (att.cumsum(-1) - 1).clamp(min=0)   # left padding: real tokens start at position 0
    try:
        o = model(input_ids=ids, attention_mask=att, position_ids=pos, **KEEP)
    except TypeError:
        KEEP = {}; o = model(input_ids=ids, attention_mask=att, position_ids=pos)
    lg = o.logits[:, -1, :].float()
    return lg[:, YES] - lg[:, NO]

def auc(s, y):
    s, y = np.asarray(s), np.asarray(y, bool)
    if y.all() or (~y).all(): return float("nan")
    r = s.argsort().argsort() + 1.0
    return (r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum())

@torch.no_grad()
def predict(items):
    model.eval(); res = {}
    for b, ids, att, _ in batches(items, 32, False):
        for i, m in zip(b, torch.sigmoid(margin(ids, att)).tolist()): res[i] = m
    model.train(); return [res[i] for i in range(len(items))]

def evaluate():
    p = predict(va_items); y = [l for _, l in va_items]
    clear = [(pp, yy >= 0.8) for pp, yy in zip(p, y) if yy >= 0.8 or yy <= 0.2]
    return auc([c[0] for c in clear], [c[1] for c in clear]), float(np.mean([(pp - yy) ** 2 for pp, yy in zip(p, y)]))

opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=a.lr, weight_decay=0.0)
total = math.ceil(len(tr_items) / a.bs / a.accum) if not a.steps else a.steps
sched = get_cosine_schedule_with_warmup(opt, int(0.03 * total), total)
lossf = torch.nn.BCEWithLogitsLoss()
a0, m0 = evaluate(); log(f"zero-shot val AUC {a0:.4f} MSE {m0:.4f}")
best, step, micro, run = a0, 0, 0, []
model.train()
for b, ids, att, ys in batches(tr_items, a.bs, True):
    loss = lossf(margin(ids, att), ys.cuda()) / a.accum
    loss.backward(); run.append(loss.item() * a.accum); micro += 1
    if micro % a.accum: continue
    torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
    opt.step(); sched.step(); opt.zero_grad(); step += 1
    if step % 50 == 0:
        log(f"step {step}/{total} loss {np.mean(run[-100:]):.4f} {torch.cuda.max_memory_allocated() / 2**30:.1f}GB")
    if step % a.eval_every == 0 or step == total:
        av, mse = evaluate(); log(f"step {step} val AUC {av:.4f} MSE {mse:.4f}")
        if av > best: best = av; model.save_pretrained(out / "adapter"); log("  saved best")
    if step >= total: break
if not (out / "adapter").exists(): model.save_pretrained(out / "adapter")
log(f"training done, best val AUC {best:.4f}")

# ------------------------------------------------------- score the bench ----
from peft import set_peft_model_state_dict
from safetensors.torch import load_file
set_peft_model_state_dict(model, load_file(str(out / "adapter" / "adapter_model.safetensors")))
bench = read(BENCH)
b_items = [(tok(prompt(r["original"], r["candidate"]), add_special_tokens=False)["input_ids"][-4096:], None) for r in bench]
t1 = time.time(); p = predict(b_items); sec = time.time() - t1
name = Path(a.out).name
with open(BENCH_DIR / f"llm_ft_{name}.jsonl", "w") as f:
    for r, s in zip(bench, p): f.write(json.dumps({"id": r["id"], "same": s}) + "\n")
json.dump({"model": f"{a.model} + LoRA ({name})", "mode": "llm-ft", "pairs_per_sec": len(bench) / sec,
           "best_val_auc": best, "zero_shot_val_auc": a0, "train_rows": len(tr_items), "total_sec": time.time() - t0},
          open(BENCH_DIR / f"llm_ft_{name}.jsonl.meta.json", "w"), indent=1)
log(f"bench scored: {len(bench)} pairs in {sec:.0f}s ({len(bench) / sec:.1f}/s, HF eager, batch 32)")
print("EXIT=0", flush=True)
