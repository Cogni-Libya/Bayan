#!/usr/bin/env python3
"""Compare extracted text of the LaTeX PDF vs the Word PDF, normalized.

Normalizations (so line-wrap / tokenization noise does not count as missing content):
- join hyphenated line breaks  "compari- son" → "comparison"
- strip glue punctuation around tokens  "(1,509)" ≈ "1,509"
- Unicode NFC (presentation-form Arabic ≈ nominal forms)
- treat '#' the same
"""
from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
GT = HERE.parent.parent / "Bayan_Final_Report.pdf"


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text.replace("\u00a0", " "))
    text = re.sub(r"Page\s+\d+\s*/\s*\d+", " ", text)
    # line-break hyphenation: word- + newline/space + word
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokens(text: str) -> list[str]:
    # drop glue punctuation as standalone tokens
    return [t.strip("()[]{}<>,;:.!?\"'“”‘’") for t in text.split()
            if t.strip("()[]{}<>,;:.!?\"'“”‘’")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("word_pdf", type=Path)
    ap.add_argument("--gt", type=Path, default=GT)
    args = ap.parse_args()

    gt_doc = fitz.open(args.gt)
    wv_doc = fitz.open(args.word_pdf)
    gt_text = normalize(" ".join(p.get_text() for p in gt_doc))
    wv_text = normalize(" ".join(p.get_text() for p in wv_doc))

    gt_toks = tokens(gt_text)
    wv_toks = tokens(wv_text)
    gw, ww = set(gt_toks), set(wv_toks)
    union = gw | ww
    jaccard = len(gw & ww) / len(union) if union else 1.0
    ratio = len(wv_toks) / len(gt_toks) if gt_toks else 1.0

    # 8-gram presence on token streams (same tokenization both sides)
    hits = miss = 0
    missing = []
    wv_set = set()
    for i in range(0, len(wv_toks) - 8):
        wv_set.add(tuple(wv_toks[i:i + 8]))
    for i in range(0, len(gt_toks) - 8, 30):
        phrase = tuple(gt_toks[i:i + 8])
        if phrase in wv_set:
            hits += 1
        else:
            miss += 1
            if len(missing) < 8:
                missing.append(" ".join(phrase))

    print(f"pages           gt={gt_doc.page_count} wv={wv_doc.page_count}")
    print(f"tokens          gt={len(gt_toks)} wv={len(wv_toks)} ratio={ratio:.3f}")
    print(f"jaccard         {jaccard:.3f}")
    print(f"8-gram          {hits}/{hits+miss} = {hits/(hits+miss):.1%}")
    tex_cmds = re.findall(r"\\[a-zA-Z]+|\^\{|[{}]", wv_text)
    labels = re.findall(r"\b(?:sec|tab|fig):", wv_text)
    print(f"raw TeX cmds    {len(tex_cmds)} {sorted(set(tex_cmds))[:10]}")
    print(f"raw labels      {len(labels)}")
    only_gt = sorted(gw - ww)[:20]
    only_wv = sorted(ww - gw)[:20]
    print("only-GT sample  ", only_gt)
    print("only-WV sample  ", only_wv)
    if missing:
        print("missing 8-grams:")
        for m in missing:
            print(" ", m)
    return 0


if __name__ == "__main__":
    sys.exit(main())
