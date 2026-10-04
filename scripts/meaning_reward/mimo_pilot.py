"""MiMo second-judge pilot on the BayanBench v2 rating round, with Marwan's pass rule fixed in advance (#48).

  python mimo_pilot.py --ratings human_ratings_v2.jsonl --out mimo_pilot.jsonl

MiMo (mimo-v2.6-pro, OpenAI-compatible API, thinking off) gets the bench judge's "same meaning" question and answers
with a 0-100 confidence (its API returns no logprobs). Kept = human meaning_majority "same" (a tie counts as not kept).
Pass rule: (1) AUC vs majority "same" >= 0.79; (2) on the outputs where Gemma 4 31B at 0.5 and the majority disagree,
MiMo at 50 sides with the humans more often than not.
"""
import argparse, concurrent.futures as cf, json, os, re, time

from openai import OpenAI

SYS = "You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or difficulty."
Q = ("Does the rewrite keep exactly the same meaning as the original: every fact, claim and qualifier preserved, and "
     "nothing added, removed, negated or changed? Rephrasing, simpler words and splitting into shorter sentences are allowed.")

ap = argparse.ArgumentParser()
ap.add_argument("--ratings", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--model", default="mimo-v2.6-pro")
ap.add_argument("--workers", type=int, default=8)
a = ap.parse_args()
key = os.environ["MIMO_API_KEY"]
client = OpenAI(api_key=key, base_url="https://api.xiaomimimo.com/v1", default_headers={"api-key": key})
rows = [json.loads(l) for l in open(a.ratings, encoding="utf-8")]
single = [r for r in rows if r["kind"] == "single"]
done = {}
if os.path.exists(a.out):
    for l in open(a.out, encoding="utf-8"):
        r = json.loads(l); done[r["task"]] = r


def ask(r):
    user = f"Original:\n{r['source']}\n\nRewrite:\n{r['output']}\n\nQuestion: {Q}\nAnswer in at most two short sentences, then end with a final line exactly in the form SCORE: N, where N (0 to 100) is your confidence that the answer is Yes."
    for attempt in range(4):
        try:
            res = client.chat.completions.create(model=a.model, temperature=0, max_completion_tokens=300,
                                                 messages=[{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                                                 extra_body={"thinking": {"type": "disabled"}})
            txt = res.choices[0].message.content or ""
            m = re.search(r"SCORE\s*[:：]\s*(\d+(?:\.\d+)?)", txt)
            return {"task": r["task"], "mimo": min(100.0, float(m.group(1))) / 100 if m else None, "raw": txt,
                    "tokens": res.usage.total_tokens}
        except Exception as e:
            time.sleep(2 * (attempt + 1)); err = str(e)[:200]
    return {"task": r["task"], "mimo": None, "raw": "ERROR " + err, "tokens": 0}


todo = [r for r in single if r["task"] not in done]
with open(a.out, "a", encoding="utf-8") as f, cf.ThreadPoolExecutor(a.workers) as ex:
    for res in ex.map(ask, todo):
        f.write(json.dumps(res, ensure_ascii=False) + "\n"); f.flush(); done[res["task"]] = res
print(f"scored {sum(d['mimo'] is not None for d in done.values())}/{len(single)}; tokens {sum(d['tokens'] for d in done.values())}")

# ---- the pass rule ----
def auc(pos, neg): return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))
ok = [r for r in single if done[r["task"]]["mimo"] is not None]
kept = lambda r: r["meaning_majority"] == "same"
pos = [done[r["task"]]["mimo"] for r in ok if kept(r)]; neg = [done[r["task"]]["mimo"] for r in ok if not kept(r)]
gpos = [r["p_same"] for r in ok if kept(r)]; gneg = [r["p_same"] for r in ok if not kept(r)]
dis = [r for r in ok if (r["p_same"] >= 0.5) != kept(r)]
side = sum((done[r["task"]]["mimo"] >= 0.5) == kept(r) for r in dis)
missed = [r for r in dis if not kept(r)]; wrong_fail = [r for r in dis if kept(r)]
res = {"n": len(ok), "kept": len(pos), "not_kept": len(neg),
       "mimo_auc": auc(pos, neg), "gemma_auc_same_items": auc(gpos, gneg),
       "disagreements": len(dis), "mimo_sides_with_humans": side,
       "of_gemma_missed_losses": [len(missed), sum(done[r['task']]['mimo'] < 0.5 for r in missed)],
       "of_gemma_wrong_fails": [len(wrong_fail), sum(done[r['task']]['mimo'] >= 0.5 for r in wrong_fail)],
       "rule1_auc_ge_0.79": auc(pos, neg) >= 0.79, "rule2_majority_with_humans": side > len(dis) / 2}
res["PASS"] = res["rule1_auc_ge_0.79"] and res["rule2_majority_with_humans"]
print(json.dumps(res, indent=1))
json.dump(res, open(os.path.splitext(a.out)[0] + "_result.json", "w"), indent=1)
