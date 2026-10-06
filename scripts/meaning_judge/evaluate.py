"""Compare every scorer on bench.jsonl.

Positive class = meaning changed. Every score is "higher = more equivalent"; a pair is rejected when
score <= t. Reported per scorer:
  AUC            changed vs same
  t@95           the threshold that rejects 95% of changed pairs
  FRR@95         share of same pairs also rejected at that threshold (lower is better)
  catch@FRR5     share of changed pairs rejected when only 5% of same pairs are
  per-kind catch at t@95
"""
import json, re, sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from paths import BENCH_DIR
from questions import combine
D = Path(sys.argv[1]) if len(sys.argv) > 1 else BENCH_DIR   # bench.jsonl + every scorer's result files

rows = {r["id"]: r for r in map(json.loads, open(D / "bench.jsonl", encoding="utf-8"))}

# ---------------------------------------------------------------- rules ----
TASH = re.compile(r"[ً-ْٰـ]")
NEG = re.compile(r"(?<!\S)[وف]?(لا|لم|لن|ليس|ليست|لست|ليسوا|غير|بدون|دون)(?!\S)")
DIG = re.compile(r"[0-9٠-٩]+")
def digits(t): return sorted(x.translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")) for x in DIG.findall(t))
for r in rows.values():
    o, c = TASH.sub("", r["original"]), TASH.sub("", r["candidate"])
    flags = []
    if digits(o) != digits(c): flags.append("num")
    if len(NEG.findall(o)) != len(NEG.findall(c)): flags.append("neg")
    if ("؟" in o or "?" in o) != ("؟" in c or "?" in c): flags.append("q")
    r["rules"] = 0.0 if flags else 1.0
    r["rule_flags"] = flags

scores = {"rules": {k: r["rules"] for k, r in rows.items()},
          "qwen_reason (Qwen3.8-27B, reasoning judge)": {k: r["qwen_reason"] for k, r in rows.items() if r["qwen_reason"] is not None}}

def load(name, path, fields):
    if not path.exists(): return
    got = {x["id"]: x for x in map(json.loads, open(path))}
    for label, fn in fields.items():
        scores[f"{name}: {label}"] = {k: fn(x) for k, x in got.items()}

qfields = {"P(same)": lambda x: x["same"], "all 4 questions": combine,
           "all 4 + rules": lambda x: combine(x) * rows[x["id"]]["rules"]}
load("Jev API", D / "jev.jsonl", qfields)
for f in sorted(p for p in D.glob("llm_*.jsonl") if not p.name.startswith("llm_ft_")):
    load(f.stem.replace("llm_", "LLM scoring "), f, qfields)
for f in sorted(D.glob("jevembed_*.jsonl")):
    load(f.stem, f, qfields)
for f in sorted(D.glob("xnli_*.jsonl")):
    load(f.stem, f, {"min(entail both ways)": lambda x: min(x["ent_fwd"], x["ent_bwd"]),
                     "entail fwd": lambda x: x["ent_fwd"], "entail bwd": lambda x: x["ent_bwd"]})
for f in sorted(D.glob("llm_ft_*.jsonl")):
    got = json.loads(open(f).readline())
    fields = {"P(same)": lambda x: x["same"]}
    if "added" in got:
        fields.update({"4 heads (min)": combine, "4 heads + no rules": lambda x: combine(x)})
        fields.pop("4 heads + no rules")
    load(f.stem.replace("llm_ft_", "FINE-TUNED "), f, fields)
for f in sorted(D.glob("ft_*.jsonl")):
    load(f.stem.replace("ft_", "FINE-TUNED "), f, {"min(both directions)": lambda x: min(x["fwd"], x["bwd"]), "original->rewrite only": lambda x: x["fwd"], "mean both": lambda x: (x["fwd"] + x["bwd"]) / 2})
for f in sorted(D.glob("rerank_*.jsonl")):
    load(f.stem, f, {"min(both directions)": lambda x: min(x["fwd"], x["bwd"])})
for f in sorted(D.glob("embed_*.jsonl")):
    load(f.stem, f, {"cosine": lambda x: x["cos"]})

def auc(pos, neg):
    pos, neg = np.asarray(pos), np.asarray(neg)
    if not len(pos) or not len(neg): return float("nan")
    allv = np.concatenate([pos, neg]); ranks = allv.argsort().argsort() + 1.0
    # average ties
    _, inv, cnt = np.unique(allv, return_inverse=True, return_counts=True)
    sums = np.bincount(inv, ranks); ranks = (sums / cnt)[inv]
    return (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))

def report(title, ids_changed, ids_same, kinds=True):
    print(f"\n## {title}  (changed {len(ids_changed)}, same {len(ids_same)})")
    print(f"{'scorer':58s} {'n':>5s} {'AUC':>6s} {'t@95':>6s} {'FRR@95':>7s} {'catch@FRR5':>10s}  per-kind catch at t@95")
    for name, sc in scores.items():
        ch = [k for k in ids_changed if k in sc]; sa = [k for k in ids_same if k in sc]
        if len(ch) < 10 or len(sa) < 10: continue
        pc = np.array([sc[k] for k in ch]); ps = np.array([sc[k] for k in sa])
        t95 = np.quantile(pc, 0.95); frr = (ps <= t95).mean()
        t5 = np.quantile(ps, 0.05); catch = (pc <= t5).mean() if name != "rules" else (pc == 0).mean()
        kk = ""
        if kinds:
            by = {}
            for k in ch: by.setdefault(rows[k]["kind"], []).append(sc[k] <= t95)
            kk = " ".join(f"{a}:{100*np.mean(b):.0f}" for a, b in sorted(by.items()) if len(b) >= 8)
        if name == "rules":
            print(f"{name:58s} {len(ch)+len(sa):5d} {'-':>6s} {'-':>6s} {100*(ps==0).mean():6.1f}% {100*(pc==0).mean():9.1f}%  (binary: flag rate on same / changed)")
        else:
            print(f"{name:58s} {len(ch)+len(sa):5d} {auc(ps, pc):6.3f} {t95:6.3f} {100*frr:6.1f}% {100*catch:9.1f}%  {kk}")

R = rows.values()
same_all = [r["id"] for r in R if r["label"] == "same"]
report("A. Known defects (DeepSeek adversarial + scripted) vs all faithful",
       [r["id"] for r in R if r["slice"] in ("adv", "planted") and r["label"] == "changed"], same_all)
report("B. DeepSeek adversarial set only",
       [r["id"] for r in R if r["slice"] == "adv" and r["label"] == "changed"],
       [r["id"] for r in R if r["slice"] == "adv" and r["label"] == "same"])
report("C. Real pipeline errors (human + Claude labels): changed vs same",
       [r["id"] for r in R if r["slice"] in ("human", "silver") and r["label"] == "changed"],
       [r["id"] for r in R if r["slice"] in ("human", "silver") and r["label"] == "same"], kinds=False)
report("D. Real pipeline errors: changed+minor vs same",
       [r["id"] for r in R if r["slice"] in ("human", "silver") and r["label"] in ("changed", "minor")],
       [r["id"] for r in R if r["slice"] in ("human", "silver") and r["label"] == "same"])
report("E. Human labels only (the user): changed vs same",
       [r["id"] for r in R if r["slice"] == "human" and r["label"] == "changed"],
       [r["id"] for r in R if r["slice"] == "human" and r["label"] == "same"], kinds=False)

print("\n## Speed")
for m in sorted(D.glob("*.meta.json")):
    j = json.load(open(m)); print(f"{m.name:40s} {j.get('pairs_per_sec', 0):8.1f} pairs/s  ({j['model']})")
if (D / "jev.jsonl").exists():
    s = [x["sec"] for x in map(json.loads, open(D / "jev.jsonl"))]
    tok = sum(x["usage"]["input_tokens"] for x in map(json.loads, open(D / "jev.jsonl")))
    print(f"Jev API: median {np.median(s):.2f}s/request (4 questions), p95 {np.quantile(s, .95):.2f}s, {tok/1e6:.2f}M input tokens")
