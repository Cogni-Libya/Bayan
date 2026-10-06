"""Best-of-N reranking: how much better can a trained simplifier get by choosing among its own candidates?

  python rerank_bestofn.py --model runs/v1-mle/best --split dev --out runs/rerank_v1-mle

Per source: greedy output, N top-p samples and N beams (pools). Every candidate is scored as if the source needs
simplifying: score = judge P(same) x clip(lead / 2, 0, 1), 0 when a gate fails (reward.py). The source itself is
also a candidate, with a fixed score c: if no rewrite beats c, the source is returned unchanged. This is the copy
decision made without knowing pair_type; pair_type is used only to grade the pick.

Strategies reported (same metrics as eval_models.py):
  greedy                     the plain model
  best_<pool>_c<c>           argmax score over the pool + copy at c
  floor_<pool>_m<t>          the simplest candidate with P(same) >= t (ties: higher P(same)); none -> copy
The judge picks and also grades here, so these numbers are an upper estimate. The bench (Gemma 4 31B) decides.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "training" / "model2"))
from reward import JudgeClient, MeaningSimplicityReward, KEEP_TYPES, LEAD_TARGET  # noqa: E402
from sari import sari_sentence  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--prefix", default="بسط: ")
ap.add_argument("--data", default="data/processed/meaning_reward/v1")
ap.add_argument("--split", default="dev")
ap.add_argument("--n", type=int, default=16)
ap.add_argument("--top-p", type=float, default=0.95)
ap.add_argument("--bs", type=int, default=32)
ap.add_argument("--judge-url", default="http://localhost:8001")
ap.add_argument("--judge-model", default="Congi-libya/bayan-meaning-judge-e2b")
ap.add_argument("--out", required=True)
ap.add_argument("--seed", type=int, default=0)
ap.add_argument("--limit", type=int, default=0, help="first N rows only (smoke test)")
ap.add_argument("--no-judge", action="store_true", help="smoke test: P(same) = 1 for every candidate")
ap.add_argument("--device", default="cuda")
a = ap.parse_args()
out_dir = Path(a.out); out_dir.mkdir(parents=True, exist_ok=True)
torch.manual_seed(a.seed)
rows = [json.loads(l) for l in open(Path(a.data) / f"{a.split}.jsonl", encoding="utf-8")]
if a.limit: rows = rows[:a.limit]
src = [r["source"] for r in rows]; types = [r["pair_type"] for r in rows]
reward = MeaningSimplicityReward(None if a.no_judge else JudgeClient(a.judge_url, a.judge_model), device=a.device)

from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForSeq2SeqLM.from_pretrained(a.model, dtype=torch.bfloat16).to(a.device).eval()
probe = tok("a")["input_ids"]; add = not (probe and probe[-1] == tok.eos_token_id)   # transformers 5.x Barthez


def ids(texts):
    x = tok(texts, add_special_tokens=not add, truncation=True, max_length=254)["input_ids"]
    return [[tok.bos_token_id] + i + [tok.eos_token_id] for i in x] if add else x


def gen(k, **kw):
    """k outputs per source, as a list of lists aligned with rows."""
    out = [None] * len(rows); order = sorted(range(len(rows)), key=lambda i: len(src[i]))
    bs = max(1, a.bs * 16 // max(k, 1)) if k > 1 else 64
    with torch.no_grad():
        for s in range(0, len(order), bs):
            b = order[s:s + bs]; x = ids([a.prefix + src[i] for i in b]); L = max(map(len, x))
            inp = torch.tensor([t + [tok.pad_token_id] * (L - len(t)) for t in x]).to(a.device)
            att = torch.tensor([[1] * len(t) + [0] * (L - len(t)) for t in x]).to(a.device)
            g = model.generate(input_ids=inp, attention_mask=att, max_length=256, num_return_sequences=k,
                               no_repeat_ngram_size=4, **kw)
            dec = [t.strip() for t in tok.batch_decode(g, skip_special_tokens=True)]
            pre = a.prefix.strip(); dec = [t[len(pre):].strip() if t.startswith(pre) else t for t in dec]
            for j, i in enumerate(b): out[i] = dec[j * k:(j + 1) * k]
    return out


t0 = time.time()
pools = {"greedy": gen(1, do_sample=False, num_beams=1)}
pools["sample"] = gen(a.n, do_sample=True, top_p=a.top_p, num_beams=1)
pools["beam"] = gen(a.n, do_sample=False, num_beams=a.n)
print(f"generated in {time.time() - t0:.0f}s", flush=True)

# score every distinct (source, candidate) once, as a rewrite of a hard sentence
cand = {i: sorted({c for p in pools.values() for c in p[i] if c.strip()}) for i in range(len(rows))}
flat = [(i, c) for i in cand for c in cand[i]]
t0 = time.time()
sc, info = reward([src[i] for i, _ in flat], [c for _, c in flat], ["generated"] * len(flat))
print(f"scored {len(flat)} candidates in {time.time() - t0:.0f}s", flush=True)
S = {}
for (i, c), s, m, ld in zip(flat, sc, info["meaning"], info["lead"]):
    S[(i, c)] = (float(s), float(m) if np.isfinite(m) else 0.0, float(ld) if np.isfinite(ld) else -9.0)
json.dump({"pools": pools, "scores": {f"{i}\t{c}": v for (i, c), v in S.items()}},
          open(out_dir / "candidates.json", "w", encoding="utf-8"), ensure_ascii=False)


def pick_best(pool, c):
    out = []
    for i in range(len(rows)):
        cs = [x for x in set(pools[pool][i] + pools["greedy"][i]) if x.strip()]
        best = max(cs, key=lambda x: S[(i, x)][0], default=src[i])
        out.append(best if S.get((i, best), (0,))[0] > c else src[i])
    return out


def pick_floor(pool, t):
    out = []
    for i in range(len(rows)):
        cs = [x for x in set(pools[pool][i] + pools["greedy"][i]) if x.strip() and S[(i, x)][1] >= t and S[(i, x)][2] > 0]
        out.append(max(cs, key=lambda x: (min(S[(i, x)][2], LEAD_TARGET), S[(i, x)][1])) if cs else src[i])
    return out


gi = [i for i in range(len(rows)) if types[i] not in KEEP_TYPES]
ki = [i for i in range(len(rows)) if types[i] in KEEP_TYPES]


def grade(out):
    rw, inf = reward(src, out, types)
    res = {"reward_generated": float(rw[gi].mean()), "keep_exact": float(rw[ki].mean()),
           "selection": 0.7 * float(rw[gi].mean()) + 0.3 * float(rw[ki].mean()),
           "sari_generated": float(np.mean([sari_sentence(src[i], out[i], [rows[i]["target"]]) for i in gi])),
           "judge_same_mean": float(np.nanmean(inf["meaning"][gi])),
           "judge_ge_0.75": float(np.mean(np.nan_to_num(inf["meaning"][gi], nan=0) >= 0.75)),
           "lead_ge2": float(np.mean(np.nan_to_num(inf["lead"][gi], nan=-9) >= 2)),
           "gates_pass": float(inf["gate"][gi].mean()),
           "copy_hard": float(np.mean([out[i].strip() == src[i].strip() for i in gi]))}
    for t in ("identity", "protected", "short"):
        ix = [i for i in ki if types[i] == t]
        if ix: res[f"keep_{t}"] = float(rw[ix].mean())
    return res


strategies = {"greedy": [p[0] for p in pools["greedy"]]}
for pool in ("sample", "beam"):
    for c in (0.0, 0.1, 0.2, 0.3):
        strategies[f"best_{pool}_c{c}"] = pick_best(pool, c)
    for t in (0.7, 0.8):
        strategies[f"floor_{pool}_m{t}"] = pick_floor(pool, t)
results = {}
for name, out in strategies.items():
    results[name] = grade(out); print(name, json.dumps(results[name]), flush=True)
    with open(out_dir / f"{name}.preds.jsonl", "w", encoding="utf-8") as f:
        for r, p in zip(rows, out):
            f.write(json.dumps({"id": r["id"], "pair_type": r["pair_type"], "prediction": p}, ensure_ascii=False) + "\n")
json.dump(results, open(out_dir / "results.json", "w"), indent=1)
print("RERANK_DONE", flush=True)
