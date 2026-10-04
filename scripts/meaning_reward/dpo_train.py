"""Student DPO on preference pairs (dpo_pairs.py), seq2seq, with an NLL anchor on the chosen output.

  python dpo_train.py --model Congi-libya/bayan-arat5-v1 --pairs pairs.jsonl --dev v1/dev.jsonl --out runs/dpo

loss = -log sigmoid(beta * ((log pi(c) - log ref(c)) - (log pi(r) - log ref(r)))) + nll * NLL(c) / |c|
The reference is the starting model, frozen; its log-probs are computed once before training.
Every --eval-every steps, greedy on v1 dev: SARI on changed rows, copy rate on hard rows, keep-rows left unchanged,
flag rate (negation / limit / condition changed, BayanBench's code flags) and numbers kept on hard rows.
Checkpoint: the lowest flag rate among checkpoints whose SARI is within --sari-slack of the starting model's.
The E2B judge is not used for selection; the bench grades the chosen model with Gemma 4 31B afterwards.
Runs under transformers 4.x.
"""
import argparse, json, math, os, random, shutil, sys, time
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer, T5Tokenizer, get_linear_schedule_with_warmup

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "training" / "model2"))
from reward import KEEP_TYPES, numbers_kept, _norm  # noqa: E402
from sari import sari_sentence  # noqa: E402
from bayanbench.measures import flags as bench_flags  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--pairs", required=True)
ap.add_argument("--dev", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--prefix", default="بسط: ")
ap.add_argument("--beta", type=float, default=0.1)
ap.add_argument("--nll", type=float, default=0.2)
ap.add_argument("--lr", type=float, default=1e-5)
ap.add_argument("--epochs", type=float, default=1.0)
ap.add_argument("--bs", type=int, default=8)
ap.add_argument("--accum", type=int, default=2)
ap.add_argument("--oversample", default="5:3,keep:2", help="repeat pairs: SEVERITY:N or keep:N, comma separated")
ap.add_argument("--warmup", type=int, default=50)
ap.add_argument("--max-len", type=int, default=256)
ap.add_argument("--eval-every", type=int, default=250)
ap.add_argument("--sari-slack", type=float, default=1.0)
ap.add_argument("--dev-limit", type=int, default=0)
ap.add_argument("--bf16", type=int, default=1)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
a = ap.parse_args()
random.seed(a.seed); torch.manual_seed(a.seed)
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
json.dump(vars(a), open(out / "config.json", "w"), ensure_ascii=False, indent=1)
t0 = time.time()
log = lambda *x: print(f"[dpo {time.time() - t0:6.0f}s]", *x, flush=True)

cfg = AutoConfig.from_pretrained(a.model)
is_t5 = cfg.model_type in ("t5", "mt5")
tok = T5Tokenizer.from_pretrained(a.model, legacy=True) if is_t5 else AutoTokenizer.from_pretrained(a.model)
policy = AutoModelForSeq2SeqLM.from_pretrained(a.model).to(a.device)
ref = AutoModelForSeq2SeqLM.from_pretrained(a.model).to(a.device).eval()
for p in ref.parameters(): p.requires_grad_(False)
amp = (lambda: torch.autocast("cuda", dtype=torch.bfloat16)) if (a.bf16 and a.device == "cuda") else (lambda: torch.autocast("cpu", enabled=False))

pairs = [json.loads(l) for l in open(a.pairs, encoding="utf-8")]
rep = {k: int(v) for k, v in (x.split(":") for x in a.oversample.split(",") if x)}
pairs = [p for p in pairs for _ in range(rep.get("keep" if p["kind"] == "keep" else str(p["severity"]), 1))]
dev = [json.loads(l) for l in open(a.dev, encoding="utf-8")]
if a.dev_limit: dev = dev[:a.dev_limit]
log(f"{len(pairs)} pairs after oversampling {rep}, {len(dev)} dev rows")


def enc_src(texts):
    e = tok([a.prefix + t for t in texts], max_length=a.max_len, truncation=True, padding=True, return_tensors="pt")
    return e["input_ids"].to(a.device), e["attention_mask"].to(a.device)


def enc_tgt(texts):
    e = tok(text_target=texts, max_length=a.max_len, truncation=True, padding=True, return_tensors="pt")
    lab = e["input_ids"].clone(); lab[e["attention_mask"] == 0] = -100
    return lab.to(a.device)


def seq_logp(model, ids, att, lab):
    """Sum of token log-probs of lab given ids, and the number of target tokens. No labels are passed to the model
    (it would compute its own loss) and no fp32 copy of the logits is made: cross_entropy per token instead."""
    with amp():
        logits = model(input_ids=ids, attention_mask=att, decoder_input_ids=model._shift_right(lab)).logits
    lp = -F.cross_entropy(logits.transpose(1, 2), lab, ignore_index=-100, reduction="none")
    mask = lab != -100
    return (lp * mask).sum(-1), mask.sum(-1)


# reference log-probs, once
ref_c, ref_r = torch.zeros(len(pairs)), torch.zeros(len(pairs))
with torch.no_grad():
    for k in range(0, len(pairs), 64):
        b = pairs[k:k + 64]; ids, att = enc_src([p["source"] for p in b])
        ref_c[k:k + len(b)] = seq_logp(ref, ids, att, enc_tgt([p["chosen"] for p in b]))[0].cpu()
        ref_r[k:k + len(b)] = seq_logp(ref, ids, att, enc_tgt([p["rejected"] for p in b]))[0].cpu()
del ref; torch.cuda.empty_cache() if a.device == "cuda" else None
log("reference log-probs done")

pre = a.prefix.strip()


def generate(texts, bs=64):
    policy.eval(); res = []
    order = sorted(range(len(texts)), key=lambda i: len(texts[i])); res = [None] * len(texts)
    with torch.no_grad():
        for k in range(0, len(order), bs):
            b = order[k:k + bs]; ids, att = enc_src([texts[i] for i in b])
            with amp():
                g = policy.generate(input_ids=ids, attention_mask=att, max_length=a.max_len, num_beams=1,
                                    do_sample=False, no_repeat_ngram_size=4)
            for i, t in zip(b, tok.batch_decode(g, skip_special_tokens=True)):
                t = t.strip(); res[i] = t[len(pre):].strip() if pre and t.startswith(pre) else t
    policy.train(); return res


def evaluate(step):
    preds = generate([r["source"] for r in dev])
    hard = [i for i, r in enumerate(dev) if r["pair_type"] not in KEEP_TYPES]
    keep = [i for i, r in enumerate(dev) if r["pair_type"] in KEEP_TYPES]
    changed = [i for i in hard if dev[i]["source"] != dev[i]["target"]]
    fl = [bench_flags(dev[i]["source"], preds[i]) for i in hard]
    flagged = [any(v for v in f.values()) for f in fl]
    with_nums = [i for i in hard if any(ch.isdigit() for ch in dev[i]["source"])]
    m = {"step": step,
         "sari_changed": sum(sari_sentence(dev[i]["source"], preds[i], [dev[i]["target"]]) for i in changed) / max(1, len(changed)),
         "copy_hard": sum(_norm(preds[i]) == _norm(dev[i]["source"]) for i in hard) / max(1, len(hard)),
         "keep_unchanged": sum(_norm(preds[i]) == _norm(dev[i]["source"]) for i in keep) / max(1, len(keep)),
         "flag_rate_hard": sum(flagged) / max(1, len(hard)),
         "numbers_kept": sum(numbers_kept(dev[i]["source"], preds[i]) for i in with_nums) / max(1, len(with_nums))}
    log("eval", json.dumps({k: round(v, 4) if isinstance(v, float) else v for k, v in m.items()}))
    d = out / f"ckpt-{step}"; policy.save_pretrained(d); tok.save_pretrained(d)
    with open(d / "pred_dev.jsonl", "w", encoding="utf-8") as f:
        for r, p in zip(dev, preds): f.write(json.dumps({"id": r["id"], "prediction": p}, ensure_ascii=False) + "\n")
    return m


opt = torch.optim.AdamW(policy.parameters(), lr=a.lr, weight_decay=0.0)
steps = math.ceil(len(pairs) * a.epochs / (a.bs * a.accum))
sched = get_linear_schedule_with_warmup(opt, a.warmup, steps)
hist = [evaluate(0)]
policy.train(); idx = list(range(len(pairs))); step = 0; run = []; micro = 0
opt.zero_grad()
while step < steps:
    random.shuffle(idx)
    for k in range(0, len(idx), a.bs):
        if step >= steps: break
        bi = idx[k:k + a.bs]; b = [pairs[i] for i in bi]
        ids, att = enc_src([p["source"] for p in b])
        pc, nc = seq_logp(policy, ids, att, enc_tgt([p["chosen"] for p in b]))
        pr, _ = seq_logp(policy, ids, att, enc_tgt([p["rejected"] for p in b]))
        rc, rr = ref_c[bi].to(a.device), ref_r[bi].to(a.device)
        margin = a.beta * ((pc - rc) - (pr - rr))
        loss = -F.logsigmoid(margin).mean() + a.nll * (-pc / nc.clamp(min=1)).mean()
        if not torch.isfinite(loss): log("non-finite loss, stopping"); steps = step; break
        (loss / a.accum).backward(); micro += 1
        run.append((loss.item(), (margin > 0).float().mean().item(), margin.mean().item()))
        if micro % a.accum: continue
        torch.nn.utils.clip_grad_norm_(policy.parameters(), 1.0); opt.step(); sched.step(); opt.zero_grad(); step += 1
        if step % 50 == 0:
            l, acc, mg = (sum(x[j] for x in run) / len(run) for j in range(3)); run = []
            log(f"step {step}/{steps} loss {l:.4f} pref-acc {acc:.3f} margin {mg:.3f}")
        if step % a.eval_every == 0 or step == steps:
            hist.append(evaluate(step))
            if a.device == "cuda": torch.cuda.empty_cache()
json.dump(hist, open(out / "eval_history.json", "w"), indent=1)

base = hist[0]
ok = [h for h in hist if h["sari_changed"] >= base["sari_changed"] - a.sari_slack]
best = min(ok, key=lambda h: (h["flag_rate_hard"], -h["sari_changed"]))
log("selected", json.dumps(best))
shutil.copytree(out / f"ckpt-{best['step']}", out / "model", dirs_exist_ok=True)
json.dump({"selected": best, "start": base}, open(out / "summary.json", "w"), indent=1)
log("DPO_TRAIN_DONE")
