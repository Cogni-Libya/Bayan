"""Targeted training rows for the multi-head verifier, aimed at the E2B epoch-2 failure modes on the bench:
small deletions inside a fluent rewrite, statement -> question flips, and false alarms on sentence splits.

Anchors are faithful pairs already in the TRAIN / VAL splits (bench sources were excluded upstream):
SAMER human rewrites (pos_samer) and real rewrites that both teachers pass confidently
(Gemma 4 31B P(same) >= 0.95 and Jev >= 0.5). Every new row gets certain labels for all four heads.

  python build_targeted_data.py            # writes $MEANING_BENCH_DIR/data_mh/targeted_{train,val}.jsonl
"""
import json, random, re
from collections import Counter
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent))
from paths import BENCH_DIR as B, VERIFIER_DATA as J
OUT = B / "data_mh"; OUT.mkdir(parents=True, exist_ok=True)
rng = random.Random(29)
read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]

jev = {r["key"]: r for r in read(J / "jev_labels.jsonl")}
gem = {r["key"]: r["p"] for r in read(B / "teacher_gemma31b.jsonl")}
from paths import leaked_sources
leak = leaked_sources()

def anchors(rows):
    out = []
    for r in rows:
        if r["src"] in leak:
            continue
        if r["origin"] == "pos_samer":
            out.append(r)
        elif r["origin"].startswith("teacher") and gem.get(r["key"], 0) >= 0.95 and jev[r["key"]]["y"] >= 0.5:
            out.append(r)
    return out

# ------------------------------------------------------------------ edits ----
PREP = ("في", "على", "من", "إلى", "عن", "مع", "بعد", "قبل", "عند", "منذ", "حتى", "بين", "خلال", "داخل", "خارج", "أمام", "تحت", "فوق")
PUNCT = "،.؛:!؟,"

def _tokens(t):
    return t.split()

def span_drop(t):
    """Remove a 2-5 word phrase inside a clause, preferring one that starts with a preposition."""
    w = _tokens(t)
    if len(w) < 8:
        return None
    starts = [i for i in range(1, len(w) - 2) if w[i].lstrip("و") in PREP or re.match(r"^[وف]?[بل](?!ا)\S{3,}$", w[i])]
    if not starts:
        starts = list(range(1, len(w) - 3))
    for _ in range(10):
        i = rng.choice(starts); n = rng.randint(2, 5)
        span = w[i:i + n]
        if i + n >= len(w) or any(x[-1] in PUNCT for x in span[:-1]):
            continue
        tail = span[-1][-1] if span[-1][-1] in PUNCT else ""
        new = w[:i] + w[i + n:]
        if tail and new[i - 1][-1] not in PUNCT:
            new[i - 1] += tail
        return " ".join(new)
    return None

def adj_drop(t):
    """Drop the adjective of a definite noun-adjective pair: «الحصان الأبيض» -> «الحصان»."""
    w = _tokens(t)
    idx = [i for i in range(1, len(w)) if re.match(r"^ال\S{3,}", w[i]) and re.match(r"^[وفبل]?ال\S{2,}", w[i - 1])
           and w[i - 1][-1] not in PUNCT]
    if not idx or len(w) < 6:
        return None
    i = rng.choice(idx)
    tail = w[i][-1] if w[i][-1] in PUNCT else ""
    new = w[:i] + w[i + 1:]
    new[i - 1] += tail
    return " ".join(new)

def question_flip(t):
    """Turn the (last) statement into a yes/no question."""
    parts = [p for p in re.split(r"(?<=[.!؟])\s+", t.strip()) if p]
    last = parts[-1].rstrip(".!؟ ")
    if len(last.split()) < 4 or last.startswith(("هل", "لماذا", "كيف", "متى", "أين", "ما ", "من ")) or "(أ)" in t:
        return None
    parts[-1] = "هل " + last + "؟"
    return " ".join(parts)

def split_pos(t):
    """Meaning-preserving split into shorter sentences at «، و» / « ثم » / «،» boundaries."""
    cands = [m for m in re.finditer(r"،\s*و(?=\S)|\s+ثم\s+|،\s+", t) if 3 <= len(t[:m.start()].split()) and len(t[m.end():].split()) >= 3]
    if not cands:
        return None
    m = rng.choice(cands)
    sep = t[m.start():m.end()]
    rest = re.sub(r"^[\u064B-\u0652]+", "", t[m.end():])   # drop the vowel marks of a removed «و»
    if "ثم" in sep:
        rest = "ثم " + rest
    return t[:m.start()].rstrip("، ") + ". " + rest

EDITS = {"neg_span_drop": (span_drop, "missing"), "neg_adj_drop": (adj_drop, "missing"),
         "neg_question": (question_flip, "contradict"), "pos_split": (split_pos, "same")}
QUOTA = {"train": {"neg_span_drop": 4000, "neg_adj_drop": 1500, "neg_question": 3000, "pos_split": 1000},
         "val": {"neg_span_drop": 150, "neg_adj_drop": 60, "neg_question": 120, "pos_split": 40}}
nsent = lambda t: len([p for p in re.split(r"(?<=[.!؟])\s+", t.strip()) if p])

def labels(kind):
    lab = {"same": 0.0, "added": 0.0, "missing": 0.0, "contradict": 0.0}
    lab[kind] = 1.0
    return lab

for split in ("train", "val"):
    anc = anchors(read(J / f"{split}.jsonl"))
    rng.shuffle(anc)
    rows, seen, c = [], set(), Counter()
    for origin, (fn, kind) in EDITS.items():
        for a in anc:
            if c[origin] >= QUOTA[split][origin]:
                break
            new = fn(a["tgt"])
            if not new or new.strip() == a["tgt"].strip() or (a["src"], new) in seen:
                continue
            seen.add((a["src"], new)); c[origin] += 1
            rows.append({"src": a["src"], "tgt": new, "origin": origin, "labels": labels(kind),
                         "anchor_origin": a["origin"], "anchor_tgt": a["tgt"], "key": f"tg_{split}_{origin}_{c[origin]}"})
    # real restructured rewrites (>= 2 more sentences than the source) that Gemma passes confidently:
    # the kind of faithful rewrite the epoch-2 student wrongly rejected
    resplit = [a for a in anc if a["origin"].startswith("teacher") and gem.get(a["key"], 0) >= 0.97
               and nsent(a["tgt"]) >= nsent(a["src"]) + 2]
    for a in resplit[: {"train": 2500, "val": 100}[split]]:
        c["pos_resplit"] += 1
        rows.append({"src": a["src"], "tgt": a["tgt"], "origin": "pos_resplit", "labels": labels("same"),
                     "anchor_origin": a["origin"], "anchor_tgt": a["tgt"], "key": f"tg_{split}_pos_resplit_{c['pos_resplit']}"})
    with open(OUT / f"targeted_{split}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(split, "anchors", len(anc), dict(c))
