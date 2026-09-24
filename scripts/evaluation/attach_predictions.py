#!/usr/bin/env python3
"""
Join a model's predictions to the reference file, producing the JSONL that score.py reads.

    uv run python scripts/evaluation/attach_predictions.py \
        --pred pred_samer.jsonl --refs refs_samer_test.jsonl --output scored_samer.jsonl

--pred  : {"id", "source", "prediction"} per line (what train.py writes; the style tag is already removed)
--refs  : {"id", "source", "references"} per line (the private evaluation pack)
Rows are matched by id, and every reference row must have a prediction.
An empty prediction is replaced by the source, which is what the app shows the reader.
"""

import argparse
import json
import sys
from pathlib import Path


def load(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--pred", required=True, type=Path)
    p.add_argument("--refs", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()

    preds = {str(r["id"]): r["prediction"] for r in load(args.pred)}
    refs = load(args.refs)
    missing = [r["id"] for r in refs if str(r["id"]) not in preds]
    if missing:
        sys.exit(f"Error: {len(missing)} reference rows have no prediction (first: {missing[:3]}). "
                 f"Wrong prediction file for {args.refs.name}?")

    empty = 0
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in refs:
            pred = preds[str(r["id"])].strip()
            if not pred:
                pred, empty = r["source"], empty + 1
            f.write(json.dumps({"id": r["id"], "source": r["source"], "prediction": pred,
                                "references": r["references"]}, ensure_ascii=False) + "\n")
    print(f"Wrote {len(refs)} rows to {args.output} ({empty} empty predictions replaced by the source)",
          file=sys.stderr)


if __name__ == "__main__":
    main()
