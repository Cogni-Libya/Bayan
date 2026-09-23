"""Model-1 behaviour on the BAREC test rows that carry tashkeel, raw vs stripped input."""
import json, re, statistics as S
D = re.compile(r"[ً-ْٰ]")
raw = [json.loads(l) for l in open("eval/barec_raw_greedy.jsonl")]
st = [json.loads(l) for l in open("eval/barec_stripped_greedy.jsonl")]
idx = [i for i, r in enumerate(raw) if D.search(r["source"])]
def kept(r):
    s = D.sub("", r["source"]).split(); p = set(D.sub("", r["prediction"]).split())
    return sum(w in p for w in s) / max(1, len(s))
out = {"n": len(idx)}
for name, rows in (("raw", raw), ("stripped", st)):
    k = [kept(rows[i]) for i in idx]
    out[name] = {"kept_pct": 100 * S.mean(k), "losing_half_pct": 100 * sum(x < .5 for x in k) / len(k)}
json.dump(out, open("eval/analyse_barec_diacritized_subset.json", "w"), indent=1); print(out)
