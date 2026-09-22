#!/usr/bin/env python3
"""
Fill in the `prediction` field of an eval JSONL by running a seq2seq model
with greedy decoding. Output is the JSONL that score.py reads.

Pipeline:
  make_eval_input.py  ->  predict.py  ->  score.py
Only the model name / checkpoint path changes between runs.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, type=Path, help="JSONL from make_eval_input.py")
    p.add_argument("--output", required=True, type=Path, help="JSONL for score.py")
    p.add_argument("--model", default="UBC-NLP/AraT5v2-base-1024", help="HF model name or checkpoint path")
    p.add_argument("--limit", type=int, default=None, help="Random sample of N rows (seeded)")
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--max-source-len", type=int, default=512)
    p.add_argument("--max-new-tokens", type=int, default=256)
    args = p.parse_args()

    with open(args.input, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]

    if args.limit and args.limit < len(rows):
        rows = random.Random(args.seed).sample(rows, args.limit)
    print(f"{len(rows)} rows from {args.input}", file=sys.stderr)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Loading {args.model} on {device}", file=sys.stderr)
    tokenizer = AutoTokenizer.from_pretrained(args.model, use_fast=False)    
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model).to(device).eval()

    for start in range(0, len(rows), args.batch_size):
        batch = rows[start:start + args.batch_size]
        enc = tokenizer(
            [r["source"] for r in batch],
            return_tensors="pt", padding=True, truncation=True, max_length=args.max_source_len,
        ).to(device)
        with torch.no_grad():
            out = model.generate(
                **enc, num_beams=1, do_sample=False, max_new_tokens=args.max_new_tokens,
            )
        for r, text in zip(batch, tokenizer.batch_decode(out, skip_special_tokens=True)):
            r["prediction"] = text.strip()
        print(f"  {min(start + args.batch_size, len(rows))}/{len(rows)}", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"Wrote {len(rows)} rows to {args.output}", file=sys.stderr)


if __name__ == "__main__":
    main()