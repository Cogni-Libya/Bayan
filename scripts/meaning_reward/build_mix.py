"""Training mix for the fluency retrain (train_mix.py): corpus v1 + SAMER L5->L3 + denoising rows.

  python build_mix.py --v1 data/processed/meaning_reward/v1 --samer SAMER_DIR --bench BENCH_DATA --out mix/

--v1     prepare_v1.py output (train.jsonl, dev.jsonl, test.jsonl); dev and test are copied to --out unchanged.
--samer  folder with SAMER's train.tsv (columns L5, L3). SAMER is licensed to the team only: never publish the mix.
--bench  BayanBench v2 data (items/dev.jsonl, items/test.jsonl). SAMER fragments that match a bench item (or, for
         8+ words, are contained in one) are dropped, so the retrain never sees bench text.
Denoising rows: 6,000 sampled v1 targets of generated rows with ~15% of words dropped and, half the time, one
adjacent pair swapped; the model learns to restore the fluent sentence under its own prefix «صحح: ».
"""
import argparse, collections, csv, json, random, re, shutil
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--v1", required=True); ap.add_argument("--samer", required=True)
ap.add_argument("--bench", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--denoise", type=int, default=6000); ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

DI = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")
norm = lambda t: " ".join(re.sub(r"[^\w\s]|_", " ", DI.sub("", t)).split())
bench = {norm(json.loads(l)["source"]) for sp in ("dev", "test") for l in open(Path(a.bench) / "items" / f"{sp}.jsonl", encoding="utf-8")}
bench_long = [b for b in bench if len(b.split()) >= 8]


def leaks(t):
    n = norm(t)
    return n in bench or (len(n.split()) >= 8 and any(n in b for b in bench_long))


v1 = [json.loads(l) for l in open(Path(a.v1) / "train.jsonl", encoding="utf-8")]
sam = list(csv.DictReader(open(Path(a.samer) / "train.tsv", encoding="utf-8"), delimiter="\t"))
rows, drop, c = [], 0, collections.Counter()
for i, r in enumerate(sam):
    s, t = r["L5"].strip(), r["L3"].strip()
    if not s or not t: continue
    if leaks(s): drop += 1; continue
    pt = "generated" if DI.sub("", s) != DI.sub("", t) else ("short" if len(s.split()) < 4 else "identity")
    c[pt] += 1; rows.append({"id": f"samer-{i}", "source": s, "target": t, "pair_type": pt})
print(f"SAMER kept {len(rows)}, dropped for bench overlap {drop}, {dict(c)}")

random.seed(a.seed)
den = []
for r in random.sample([r for r in v1 if r["pair_type"] == "generated"], a.denoise):
    w = r["target"].split()
    if len(w) < 6: continue
    k = [x for x in w if random.random() > 0.15]
    if len(k) > 3 and random.random() < 0.5:
        j = random.randrange(len(k) - 1); k[j], k[j + 1] = k[j + 1], k[j]
    if k == w: continue
    den.append({"id": f"den-{r['id']}", "source": " ".join(k), "target": r["target"], "pair_type": "denoise", "prefix": "صحح: "})

allr = v1 + rows + den; random.shuffle(allr)
with open(out / "train_mix.jsonl", "w", encoding="utf-8") as f:
    for r in allr: f.write(json.dumps(r, ensure_ascii=False) + "\n")
for sp in ("dev", "test"): shutil.copy(Path(a.v1) / f"{sp}.jsonl", out / f"{sp}.jsonl")
print(f"train_mix rows {len(allr)}: {dict(collections.Counter(r['pair_type'] for r in allr))}")
