"""Train the seq2seq simplifier on corpus v1 with MLE + Minimum Risk Training against the meaning/simplicity reward.

    loss = MLE(target) + lambda * MRT
    MRT  = mean over sources of  sum_y Q(y|x) * (1 - reward(x, y))
           y ranges over k sampled outputs plus the corpus target (deduplicated);
           Q = softmax over that set of alpha * log p(y|x)   (Shen et al., 2016)

The MLE term keeps the model anchored to corpus v1; the MRT term moves probability toward its own outputs that keep
the meaning AND are simpler (reward.py), and toward leaving easy / protected text unchanged.
--mrt-weight 0 is the plain-MLE baseline (same code, same checkpoint selection).

Checkpoint selection on dev (every --eval-every steps, greedy decoding):
    selection = 0.7 * mean reward on generated rows + 0.3 * exact-copy rate on identity / protected / short rows
(the 70/30 mix corpus v1 is built with). Also logged: SARI on generated rows, judge P(same), share with lead >= 2,
numbers kept.

  # judge server first (same GPU): bash serve_judge.sh
  python train_mrt.py --run v1-mle --model moussaKam/AraBART --mrt-weight 0 --epochs 10 --lr 5e-5
  python train_mrt.py --run v1-mrt --model runs/v1-mle/best --mrt-weight 0.3 --epochs 2 --lr 1e-5
"""
import argparse, json, math, os, random, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "training" / "model2"))
from reward import JudgeClient, MeaningSimplicityReward, KEEP_TYPES  # noqa: E402
from sari import sari_sentence  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--run", required=True)
ap.add_argument("--model", default="moussaKam/AraBART")
ap.add_argument("--data", default="data/processed/meaning_reward/v1")
ap.add_argument("--out", default="runs")
ap.add_argument("--prefix", default="بسط: ")          # AraBART: no shadda (it becomes <unk>)
ap.add_argument("--epochs", type=float, default=10)
ap.add_argument("--max-steps", type=int, default=0)
ap.add_argument("--lr", type=float, default=5e-5)
ap.add_argument("--bs", type=int, default=16)
ap.add_argument("--warmup", type=int, default=200)
ap.add_argument("--max-len", type=int, default=256)
ap.add_argument("--mrt-weight", type=float, default=0.0, help="lambda; 0 = plain MLE")
ap.add_argument("--k", type=int, default=4, help="samples per source for MRT")
ap.add_argument("--alpha", type=float, default=0.1, help="sharpness of Q over the candidate set (on summed log-prob)")
ap.add_argument("--top-p", type=float, default=0.95)
ap.add_argument("--include-ref", type=int, default=1)
ap.add_argument("--meaning-gate", type=float, default=None,
                help="reward = simplicity if judge P(same) >= gate else 0 (default: P(same) x simplicity)")
ap.add_argument("--judge-url", default="http://localhost:8001")
ap.add_argument("--judge-model", default="Congi-libya/bayan-meaning-judge-e2b")
ap.add_argument("--eval-every", type=int, default=300)
ap.add_argument("--n-dev-gen", type=int, default=500)
ap.add_argument("--n-dev-keep", type=int, default=200)
ap.add_argument("--patience", type=int, default=5)
ap.add_argument("--bf16", type=int, default=1)
ap.add_argument("--seed", type=int, default=42)
ap.add_argument("--no-judge", type=int, default=0, help="smoke test only: meaning fixed at 1")
ap.add_argument("--final-n", type=int, default=0, help="limit the final dev pass to N rows (0 = all; smoke tests)")
a = ap.parse_args()

random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
run = Path(a.out) / a.run; run.mkdir(parents=True, exist_ok=True)
json.dump(vars(a), open(run / "config.json", "w"), ensure_ascii=False, indent=1)
t0 = time.time()
logf = open(run / "train.log", "a")
def log(*x):
    s = f"[{a.run} {time.time() - t0:7.0f}s] " + " ".join(map(str, x)); print(s, flush=True); logf.write(s + "\n"); logf.flush()

read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]
train = read(Path(a.data) / "train.jsonl"); dev = read(Path(a.data) / "dev.jsonl")
rng = random.Random(a.seed)
dev_gen = rng.sample([r for r in dev if r["pair_type"] not in KEEP_TYPES], min(a.n_dev_gen, sum(r["pair_type"] not in KEEP_TYPES for r in dev)))
dev_keep = rng.sample([r for r in dev if r["pair_type"] in KEEP_TYPES], min(a.n_dev_keep, sum(r["pair_type"] in KEEP_TYPES for r in dev)))
dev_sel = dev_gen + dev_keep
log(f"train {len(train)}  dev selection {len(dev_gen)} generated + {len(dev_keep)} keep-type")

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, get_linear_schedule_with_warmup
dev_t = "cuda" if torch.cuda.is_available() else "cpu"
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForSeq2SeqLM.from_pretrained(a.model).to(dev_t)
amp = lambda: torch.autocast(dev_t, dtype=torch.bfloat16, enabled=bool(a.bf16) and dev_t == "cuda")
log("model", a.model, f"{sum(p.numel() for p in model.parameters()) / 1e6:.0f}M params on {dev_t}")

judge = None if a.no_judge else JudgeClient(a.judge_url, a.judge_model)
reward = MeaningSimplicityReward(judge, device=dev_t, meaning_gate=a.meaning_gate)

# transformers 5.x's Barthez (AraBART) tokenizer adds no <s> ... </s>; 4.46 did. Without </s> in the labels the model
# never learns to stop (it ran on to max length). Add them ourselves whenever the tokenizer doesn't.
_probe = tok("a")["input_ids"]
ADD_SPECIAL = not (_probe and _probe[-1] == tok.eos_token_id)
log("adding <s> </s> manually:", ADD_SPECIAL)

def _ids(texts):
    ids = tok(texts, add_special_tokens=not ADD_SPECIAL, truncation=True, max_length=a.max_len - 2)["input_ids"]
    if ADD_SPECIAL:
        ids = [[tok.bos_token_id] + x + [tok.eos_token_id] for x in ids]
    return ids

def _pad(ids, value):
    L = max(len(x) for x in ids)
    return torch.tensor([x + [value] * (L - len(x)) for x in ids])

def enc(sources):
    ids = _ids([a.prefix + s for s in sources])
    return {"input_ids": _pad(ids, tok.pad_token_id).to(dev_t),
            "attention_mask": _pad([[1] * len(x) for x in ids], 0).to(dev_t)}

def labels_for(targets):
    return _pad(_ids(targets), -100).to(dev_t)

def seq_logprob(src_enc, targets):
    """Summed log p(target | source) per row (teacher forcing); differentiable."""
    lab = labels_for(targets)
    out = model(**src_enc, labels=lab)
    lp = torch.log_softmax(out.logits.float(), -1)
    mask = lab != -100
    tok_lp = lp.gather(-1, lab.clamp(min=0).unsqueeze(-1)).squeeze(-1) * mask
    return tok_lp.sum(-1), mask.sum(-1)

@torch.no_grad()
def generate(sources, sample=False, k=1, bs=64):
    model.eval(); outs = []
    for i in range(0, len(sources), bs):
        e = enc(sources[i:i + bs])
        with amp():
            g = model.generate(**e, max_length=a.max_len, do_sample=sample, top_p=a.top_p if sample else None,
                               num_beams=1, num_return_sequences=k, no_repeat_ngram_size=4)
        dec = [t.strip() for t in tok.batch_decode(g, skip_special_tokens=True)]
        pre = a.prefix.strip()
        outs += [t[len(pre):].strip() if t.startswith(pre) else t for t in dec]   # an echoed prefix is not output
    model.train(); return outs

def evaluate(step):
    preds = generate([r["source"] for r in dev_sel])
    rw, info = reward([r["source"] for r in dev_sel], preds, [r["pair_type"] for r in dev_sel])
    g = np.arange(len(dev_gen)); kp = np.arange(len(dev_gen), len(dev_sel))
    m = info["meaning"][g]; ld = info["lead"][g]
    res = {"step": step,
           "reward_generated": float(rw[g].mean()),
           "keep_exact": float(rw[kp].mean()) if len(kp) else float("nan"),
           "sari_generated": float(np.mean([sari_sentence(dev_gen[i]["source"], preds[i], [dev_gen[i]["target"]]) for i in g])),
           "judge_same_mean": float(np.nanmean(m)) if np.isfinite(m).any() else float("nan"),
           "lead_ge2": float(np.mean(np.nan_to_num(ld, nan=-9) >= 2.0)),
           "gates_pass": float(info["gate"][g].mean()),
           "copy_generated": float(np.mean([preds[i].strip() == dev_gen[i]["source"].strip() for i in g]))}
    res["selection"] = 0.7 * res["reward_generated"] + 0.3 * (0 if math.isnan(res["keep_exact"]) else res["keep_exact"])
    return res, preds

opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
steps_per_epoch = math.ceil(len(train) / a.bs)
total = a.max_steps or int(steps_per_epoch * a.epochs)
sched = get_linear_schedule_with_warmup(opt, min(a.warmup, total // 10), total)
history, best, bad, step = [], -1.0, 0, 0
r0, _ = evaluate(0); history.append(r0); log("eval", json.dumps(r0)); best = r0["selection"]
model.save_pretrained(run / "best"); tok.save_pretrained(run / "best")
model.train()
stats = []
while step < total:
    order = list(range(len(train))); rng.shuffle(order)
    for i in range(0, len(order), a.bs):
        if step >= total: break
        batch = [train[j] for j in order[i:i + a.bs]]
        S = [r["source"] for r in batch]; T = [r["target"] for r in batch]; P = [r["pair_type"] for r in batch]
        e = enc(S)
        with amp():
            mle = model(**e, labels=labels_for(T)).loss
        loss = mle; mrt_val = torch.tensor(0.0); mean_r = float("nan")
        if a.mrt_weight > 0:
            samples = generate(S, sample=True, k=a.k)
            cand, owner = [], []
            for b in range(len(batch)):
                cs = list(dict.fromkeys(samples[b * a.k:(b + 1) * a.k] + ([T[b]] if a.include_ref else [])))
                cand += cs; owner += [b] * len(cs)
            rw, _ = reward([S[o] for o in owner], cand, [P[o] for o in owner])
            rw_t = torch.tensor(rw, device=dev_t)
            src_rep = {k_: v.index_select(0, torch.tensor(owner, device=dev_t)) for k_, v in e.items()}
            with amp():
                lp, _ = seq_logprob(src_rep, cand)
            own = torch.tensor(owner, device=dev_t)
            risk = []
            for b in range(len(batch)):
                idx = (own == b).nonzero().squeeze(-1)
                q = torch.softmax(a.alpha * lp[idx], 0)
                risk.append((q * (1 - rw_t[idx])).sum())
            mrt_val = torch.stack(risk).mean()
            loss = mle + a.mrt_weight * mrt_val
            mean_r = float(rw.mean())
        opt.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        opt.step(); sched.step(); step += 1
        if not math.isfinite(loss.item()):
            log("NON-FINITE LOSS, stopping"); total = step; break
        stats.append((mle.item(), mrt_val.item(), mean_r))
        if step % 50 == 0:
            s = np.array(stats[-50:], dtype=float)
            log(f"step {step}/{total} mle {s[:,0].mean():.4f} mrt {s[:,1].mean():.4f} sample-reward {np.nanmean(s[:,2]) if np.isfinite(s[:,2]).any() else float('nan'):.3f}")
        if step % a.eval_every == 0 or step == total:
            res, preds = evaluate(step); history.append(res); log("eval", json.dumps(res))
            if res["selection"] > best:
                best, bad = res["selection"], 0
                model.save_pretrained(run / "best"); tok.save_pretrained(run / "best"); log("  saved best")
            else:
                bad += 1
                if bad >= a.patience:
                    log("early stop"); total = step; break
json.dump(history, open(run / "eval_history.json", "w"), indent=1)

# final: the best checkpoint, greedy on the whole dev split, per pair_type
model = AutoModelForSeq2SeqLM.from_pretrained(run / "best").to(dev_t)
if a.final_n: dev = dev[:a.final_n]
preds = generate([r["source"] for r in dev])
rw, info = reward([r["source"] for r in dev], preds, [r["pair_type"] for r in dev])
with open(run / "pred_dev.jsonl", "w", encoding="utf-8") as f:
    for r, p_, x, m_, l_ in zip(dev, preds, rw, info["meaning"], info["lead"]):
        f.write(json.dumps({"id": r["id"], "pair_type": r["pair_type"], "source": r["source"], "prediction": p_,
                            "reward": float(x), "judge_same": None if np.isnan(m_) else float(m_),
                            "lead": None if np.isnan(l_) else float(l_)}, ensure_ascii=False) + "\n")
summary = {"best_selection": best, "steps": step, "train_seconds": time.time() - t0}
for t in ("generated", "identity", "protected", "short"):
    ix = [i for i, r in enumerate(dev) if r["pair_type"] == t]
    if ix:
        summary[f"dev_{t}_reward"] = float(rw[ix].mean())
gi = [i for i, r in enumerate(dev) if r["pair_type"] == "generated"]
summary["dev_generated_sari"] = float(np.mean([sari_sentence(dev[i]["source"], preds[i], [dev[i]["target"]]) for i in gi]))
summary["dev_generated_judge_same"] = float(np.nanmean(info["meaning"][gi]))
summary["dev_generated_lead_ge2"] = float(np.mean(np.nan_to_num(info["lead"][gi], nan=-9) >= 2))
json.dump(summary, open(run / "summary.json", "w"), indent=1)
log("done", json.dumps(summary))
