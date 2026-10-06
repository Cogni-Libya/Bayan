"""Build the frozen meaning-equivalence test set (bench.jsonl).

Every row: id, slice, original, candidate, label (same / minor / changed), kind, qwen_reason (the
production Qwen3.8-27B reasoning judge score, when one exists).

Slices
  adv      DeepSeek-written rewrites: 1 faithful + add / delete / negate / question per sentence
  human    pipeline outputs labelled by the user (pilot review + mixed batch)
  silver   corpus-v1 pairs labelled blind by Claude (S / M / C)
  planted  scripted defects applied to silver pairs labelled S (label certain: changed)
  identity original returned unchanged (must be same)
"""
import json, random, re, sys
from pathlib import Path

import polars as pl

MAIN = Path(sys.argv[1])            # main checkout
V1 = Path(sys.argv[2])              # corpus-v1 worktree
OUT = Path(sys.argv[3])
rng = random.Random(7)
rows = []

cal = pl.read_parquet(V1 / "data/processed/v1_final/judge_calibration.parquet")
for i, r in enumerate(cal.iter_rows(named=True)):
    if r["set"] == "adversarial":
        rows.append(dict(id=f"adv{i}", slice="adv", original=r["original"], candidate=r["candidate"],
                         label="same" if r["label"] == "faithful" else "changed", kind=r["label"],
                         qwen_reason=r["score"]))
    else:
        rows.append(dict(id=f"hum{i}", slice="human", original=r["original"], candidate=r["candidate"],
                         label=r["label"], kind="pilot", qwen_reason=r["score"]))

mb = MAIN / "data/processed/review_mixed_batch"
lab = {}
for line in open(mb / "annotations/Abdulrahman.jsonl", encoding="utf-8"):
    a = json.loads(line); lab[a["item"]] = a.get("meaning")
for line in open(mb / "review_pairs.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if lab.get(r["id"]) in ("same", "minor", "changed"):
        rows.append(dict(id=f"mix_{r['id']}", slice="human", original=r["original"], candidate=r["candidate"],
                         label=lab[r["id"]], kind="mixed", qwen_reason=None))

audit = {a["n"]: a for a in json.load(open(V1 / "data/processed/judge_audit_v1/audit_labels.json"))}
sample = [json.loads(l) for l in open(V1 / "data/processed/judge_audit_v1/sample.jsonl", encoding="utf-8")]
LBL = {"S": "same", "M": "minor", "C": "changed"}
for s in sample:
    a = audit[s["n"]]
    rows.append(dict(id=f"sil{s['n']}", slice="silver", original=s["src"], candidate=s["tgt"],
                     label=LBL[a["label"]], kind=a["etype"] or "S", qwen_reason=s["eq"]))

# ------------------------------------------------------------------ planted defects ----
NEG = r"(?<!\S)(لا|لم|لن|ليس|ليست|لست|ليسوا)(?!\S)"
NOT_VERB = {"يوم", "يونيو", "يوليو", "يناير", "يد", "يمين", "يسار", "يونس", "يوسف"}

def negate(t):
    if re.search(NEG, t):
        return re.sub(r"\s+", " ", re.sub(NEG, "", t, count=1)).strip()
    for a, b in (("كان ", "لم يكن "), ("كانت ", "لم تكن "), ("يمكن ", "لا يمكن "), ("يجب ", "لا يجب ")):
        if a in t:
            return t.replace(a, b, 1)
    toks = t.split()
    for k, w in enumerate(toks):
        c = w.lstrip("و")
        if c.startswith(("ي", "ت")) and len(c) >= 4 and not c.endswith(("ة", "ات")) and c not in NOT_VERB and not c.startswith("ال"):
            return " ".join(toks[:k] + ["لا"] + toks[k:])
    return None

def delete(t):
    segs = [x.strip() for x in re.split(r"[،؛,]", t) if x.strip()]
    if len(segs) >= 2:
        cand = [k for k in range(1, len(segs)) if len(segs[k].split()) >= 3]
        if cand:
            k = rng.choice(cand)
            out = "، ".join(s for j, s in enumerate(segs) if j != k)
            return out if out.endswith((".", "؟", "!")) else out + "."
    toks = t.split()
    cuts = [k for k, w in enumerate(toks) if w.startswith("و") and len(w) > 2 and 4 <= k <= len(toks) - 3]
    if cuts:
        k = rng.choice(cuts)
        return " ".join(toks[:k]).rstrip("،,") + "."
    return None

DETAILS = ["في عام 1987", "في القاهرة", "بشكل مؤقت", "للمرة الأولى", "بسبب الحرب", "دون علم أحد",
           "بعد موافقة الحكومة", "في فصل الشتاء", "بمساعدة الجيش", "على نفقة الدولة"]

def add_detail(t):
    body = t.rstrip(".؟!").rstrip()
    end = t[len(body):] or "."
    return f"{body} {rng.choice(DETAILS)}{end}"

def add_clause(t, other):
    seg = re.split(r"[،؛,.؟!]", other)[0].strip()
    if len(seg.split()) < 4:
        return None
    body = t.rstrip(".؟!").rstrip()
    return f"{body}، و{seg}."

DIG = re.compile(r"[0-9٠-٩]+")
def number(t):
    m = [x for x in DIG.finditer(t)]
    if not m:
        return None
    x = rng.choice(m); s = x.group()
    tr = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    v = int(s.translate(tr)); nv = v + rng.choice([1, 2, 3, 5, 10]) if v > 20 else v + rng.choice([1, 2, 3])
    ns = str(nv) if s.isascii() else str(nv).translate(str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩"))
    return t[:x.start()] + ns + t[x.end():]

good = [s for s in sample if audit[s["n"]]["label"] == "S" and len(s["tgt"].split()) >= 8]
rng.shuffle(good)
others = [s["tgt"] for s in sample]
count = {}
for s in good[:260]:
    t = s["tgt"]
    fns = [("negate", negate(t)), ("delete", delete(t)), ("add_detail", add_detail(t)),
           ("add_clause", add_clause(t, rng.choice(others))), ("number", number(t))]
    fns = [(k, c) for k, c in fns if c and c != t]
    # two defects per source, numbers always kept when present (they are rare)
    pick = [f for f in fns if f[0] == "number"] + rng.sample([f for f in fns if f[0] != "number"], k=min(2, len([f for f in fns if f[0] != "number"])))
    for k, c in pick:
        count[k] = count.get(k, 0) + 1
        rows.append(dict(id=f"pl{s['n']}_{k}", slice="planted", original=s["src"], candidate=c,
                         label="changed", kind=k, qwen_reason=None))

for s in good[260:360]:
    rows.append(dict(id=f"id{s['n']}", slice="identity", original=s["src"], candidate=s["src"],
                     label="same", kind="identity", qwen_reason=None))

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
df = pl.DataFrame(rows)
print(df.group_by("slice", "label").len().sort("slice", "label"))
print("planted kinds", count, "total", len(rows))
