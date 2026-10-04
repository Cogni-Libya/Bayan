"""Preference pairs for student DPO from scored candidates (dpo_sample.py output).

  python dpo_pairs.py --data v1/train.jsonl --cands cands.jsonl --out pairs.jsonl --judge-url http://localhost:8001

Every candidate of a `generated` source is checked as a rewrite:
  gates     every number and Latin token kept, corpus v1's structure gates (MCQ options, honorifics, verses), non-empty
  flags     negation / limit / condition changed (BayanBench's code flags)
  judge     E2B judge: P(same), P(added), P(missing), P(contradict)
  lead      CAMeL level of the source (MCQ stem) minus that of the output's hardest sentence
Chosen (generated): the candidate that passes the gates, P(same) >= 0.75, P(missing) < 0.5, P(contradict) < 0.3,
no flag with P(contradict) >= 0.15, lead >= 1; the most simplified one (lead capped at 2), then the highest P(same).
If none qualifies, the corpus target.
Rejected (generated), worst first, up to --max-rejected:
  5 contradiction (P(contradict) >= 0.5, or a flag with P(contradict) >= 0.3)
  4 gate failure (a number, Latin token, MCQ option, honorific or verse lost)
  3 meaning lost (P(missing) >= 0.5 or P(same) < 0.5)
  2 copy of the source
  1 no readability gain (lead <= 0)
Keep-type sources (identity / protected / short): chosen = the source unchanged, rejected = candidates that changed it.
The judge is the training signal only; the bench grades with Gemma 4 31B.
"""
import argparse, json, re, sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent))
from reward import JudgeClient, KEEP_TYPES, numbers_kept, _norm  # noqa: E402
from corpus_constraints import mcq_stem, readability_units, structure_gates  # noqa: E402
from bayanbench.measures import flags as bench_flags  # noqa: E402

LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]*")

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--cands", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--judge-url", default="http://localhost:8001")
ap.add_argument("--judge-model", default="Congi-libya/bayan-meaning-judge-e2b")
ap.add_argument("--max-rejected", type=int, default=2)
ap.add_argument("--device", default=None)
ap.add_argument("--no-judge", action="store_true", help="smoke test: every candidate gets P(same)=1, others 0")
a = ap.parse_args()

rows = {str(r["id"]): r for r in map(json.loads, open(a.data, encoding="utf-8"))}
cands = [json.loads(l) for l in open(a.cands, encoding="utf-8")]


def latin_kept(src, out):
    s, o = Counter(LATIN.findall(src)), Counter(LATIN.findall(out))
    return all(o[k] >= v for k, v in s.items())


# 1) every distinct rewrite of a generated source, with its gates and flags
gen = []                                    # (row id, candidate, gate ok, flagged)
for c in cands:
    r = rows[str(c["id"])]
    if r["pair_type"] in KEEP_TYPES:
        continue
    src = r["source"]
    for t in dict.fromkeys([x for x in c["candidates"] if x.strip()] + [r["target"]]):
        if _norm(t) == _norm(src):
            gen.append((str(c["id"]), t, None, False)); continue           # a copy: no judge needed
        ok = numbers_kept(src, t) and latin_kept(src, t) and all(structure_gates(src, t).values())
        fl = any(v for v in bench_flags(src, t).values())
        gen.append((str(c["id"]), t, ok, fl))
print(f"{len(gen)} distinct candidates on {sum(1 for c in cands if rows[str(c['id'])]['pair_type'] not in KEEP_TYPES)} generated sources", flush=True)

# 2) CAMeL lead and judge scores for the gated non-copy candidates
from camel_readability import CamelReadability  # noqa: E402
camel = CamelReadability(device=a.device)
live = [k for k, (_, _, ok, _) in enumerate(gen) if ok]
units = {k: readability_units(gen[k][1]) or [gen[k][1]] for k in live}
texts = sorted({mcq_stem(rows[gen[k][0]]["source"]) for k in live} | {u for k in live for u in units[k]})
lv = dict(zip(texts, map(float, camel.expected_level(camel.predict_probs(texts)))))
lead = {k: lv[mcq_stem(rows[gen[k][0]]["source"])] - max(lv[u] for u in units[k]) for k in live}
print(f"CAMeL levels for {len(texts)} texts", flush=True)
if a.no_judge:
    P = {k: (1.0, 0.0, 0.0, 0.0) for k in live}
else:
    judge = JudgeClient(a.judge_url, a.judge_model)
    p = judge.score([(rows[gen[k][0]]["source"], gen[k][1]) for k in live])
    P = {k: tuple(map(float, row)) for k, row in zip(live, p)}
print(f"judged {len(P)} candidates", flush=True)


def severity(k):
    _, t, ok, fl = gen[k]
    if ok is None: return 2                                      # copy
    if not ok: return 4                                          # gate failure
    same, added, missing, contra = P[k]
    if contra >= 0.5 or (fl and contra >= 0.3): return 5
    if missing >= 0.5 or same < 0.5: return 3
    if lead[k] <= 0: return 1
    return 0


def qualifies(k):
    _, _, ok, fl = gen[k]
    if not ok: return False
    same, added, missing, contra = P[k]
    return same >= 0.75 and missing < 0.5 and contra < 0.3 and not (fl and contra >= 0.15) and lead[k] >= 1


by_row = {}
for k, g in enumerate(gen):
    by_row.setdefault(g[0], []).append(k)

pairs, stats = [], Counter()
for c in cands:
    rid = str(c["id"]); r = rows[rid]; src = r["source"]
    if r["pair_type"] in KEEP_TYPES:
        changed = list(dict.fromkeys(x for x in c["candidates"] if x.strip() and _norm(x) != _norm(src)))
        for t in changed[:a.max_rejected]:
            pairs.append({"id": rid, "source": src, "chosen": src, "rejected": t, "kind": "keep", "severity": 2})
        stats["keep sources"] += 1; stats["keep pairs"] += len(changed[:a.max_rejected])
        continue
    ks = by_row.get(rid, [])
    good = [k for k in ks if qualifies(k)]
    if good:
        ch = max(good, key=lambda k: (min(lead[k], 2.0), P[k][0])); chosen = gen[ch][1]; stats["chosen: own candidate"] += 1
    else:
        ch = None; chosen = r["target"]; stats["chosen: corpus target"] += 1
    bad = sorted((k for k in ks if k != ch and gen[k][1] != chosen and severity(k) >= 1),
                 key=lambda k: (-severity(k), P.get(k, (1, 0, 0, 0))[0]))
    for k in bad[:a.max_rejected]:
        pairs.append({"id": rid, "source": src, "chosen": chosen, "rejected": gen[k][1], "kind": "generated",
                      "severity": severity(k)})
        stats[f"rejected severity {severity(k)}"] += 1
    if not bad: stats["generated sources with no rejected"] += 1

with open(a.out, "w", encoding="utf-8") as f:
    for p in pairs: f.write(json.dumps(p, ensure_ascii=False) + "\n")
print(f"wrote {len(pairs)} pairs to {a.out}", flush=True)
for k, v in sorted(stats.items()): print(f"  {k}: {v}", flush=True)
