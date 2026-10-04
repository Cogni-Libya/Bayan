"""Audit an exported corpus against the issue #44 rules. Code only, no model; exits 1 on any violation.

    uv run python scripts/check_corpus.py data/processed/corpus_v1            # synthetic_{train,dev,test}.jsonl
    uv run python scripts/check_corpus.py data/processed/corpus_v1 --show 5   # print examples per failed check

Generated pairs must: come from a route-"hard" source (not protected, not verse-quoting, not short),
keep MCQ option labels in order, keep every honorific and quoted verse, end the way the source ends,
be tier A/B with readability_lead > 0. Every pair, of any type, must be free of tashkeel; identity-type
pairs (protected / short / identity) must have output == input.
"""
from __future__ import annotations

import argparse
import collections
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import MIN_READABILITY_LEAD, PROTECTED_SOURCES
from corpus_constraints import (
    TASHKEEL, has_verse_marker, honorifics_preserved, is_short, normalize_ending, options_preserved,
    verses_preserved,
)

IDENTITY_TYPES = ("protected", "short", "identity")


def violations(r: dict) -> list[str]:
    s, t, kind = r["original_text"], r["simplified_text"], r["pair_type"]
    out = []
    if TASHKEEL.search(s) or TASHKEEL.search(t):
        out.append("tashkeel present")
    if kind in IDENTITY_TYPES:
        if s != t:
            out.append(f"{kind}: output differs from input")
        return out
    if kind != "generated":
        return [f"unknown pair_type {kind!r}"]
    if r.get("Source") in PROTECTED_SOURCES:
        out.append("generated from a protected source (scripture / Hanging Odes)")
    if has_verse_marker(s):
        out.append("generated from a verse-quoting source")
    if is_short(s):
        out.append("generated from a source of 5 words or fewer")
    if not options_preserved(s, t):
        out.append("MCQ option labels not preserved")
    if not honorifics_preserved(s, t):
        out.append("honorific dropped")
    if not verses_preserved(s, t):
        out.append("quoted verse changed")
    if normalize_ending(s, t) != t.strip():
        out.append("ending differs from the source's")
    if r.get("acceptance_tier") not in ("A", "B"):
        out.append("not tier A/B")
    if (r.get("readability_lead") or 0) < MIN_READABILITY_LEAD:
        out.append(f"readability_lead < {MIN_READABILITY_LEAD}")
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("corpus_dir", type=Path)
    ap.add_argument("--show", type=int, default=0, help="print this many examples per failed check")
    args = ap.parse_args()

    counts, by_type, examples = collections.Counter(), collections.Counter(), collections.defaultdict(list)
    for split in ("train", "dev", "test"):
        for line in open(args.corpus_dir / f"synthetic_{split}.jsonl", encoding="utf-8"):
            r = json.loads(line)
            by_type[(split, r["pair_type"])] += 1
            for v in violations(r):
                counts[v] += 1
                if len(examples[v]) < args.show:
                    examples[v].append((split, r["ID"], r["original_text"], r["simplified_text"]))

    print("rows:", dict(sorted(by_type.items())))
    if not counts:
        print("check_corpus: 0 violations")
        return
    for v, n in counts.most_common():
        print(f"{n:6}  {v}")
        for split, i, s, t in examples[v]:
            print(f"        [{split} {i}] {s[:90]}\n{'':17}-> {t[:90]}")
    sys.exit(1)


if __name__ == "__main__":
    main()
