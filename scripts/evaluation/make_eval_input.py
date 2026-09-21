#!/usr/bin/env python3
"""
Convert a locked test file (SAMER TSV or BAREC CSV) into the JSONL that
scripts/evaluation/score.py reads:
    {"id", "source", "prediction", "references"}

SAMER (Novel, Chapter, L5, L4, L3, Line): source = L5, references = [L3] (L3 only, never L4).
BAREC (Sentence):                          source = Sentence, references = [].
prediction: --prediction-column if given, otherwise a copy of source (copy baseline).
No rows are dropped or downsampled, including SAMER rows where L5 == L3.
"""

import argparse
import csv
import json
import sys
from pathlib import Path

FORMATS = {
    # name: (delimiter, source column, reference column or None)
    "samer": ("\t", "L5", "L3"),
    "barec": (",", "Sentence", None),
}


def convert(path: Path, fmt: str, prediction_column: str | None) -> list[dict]:
    delimiter, src_col, ref_col = FORMATS[fmt]
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        header = reader.fieldnames or []

        needed = [src_col] + ([ref_col] if ref_col else [])
        if prediction_column:
            needed.append(prediction_column)
        missing = [c for c in needed if c not in header]
        if missing:
            sys.exit(f"Error: column(s) {missing} not in {path.name}. Found: {header}")

        rows = []
        for idx, row in enumerate(reader):
            source = row[src_col].strip()
            prediction = row[prediction_column].strip() if prediction_column else source
            references = [row[ref_col].strip()] if ref_col else []
            rows.append({
                "id": f"{fmt}_{idx}",
                "source": source,
                "prediction": prediction,
                "references": references,
            })
    return rows


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--format", required=True, choices=list(FORMATS))
    p.add_argument("--prediction-column", default=None,
                   help="Column holding predictions. Default: copy source (copy baseline).")
    p.add_argument("--expected-rows", type=int, default=None,
                   help="Fail if the row count differs (7286 for BAREC test, 3277 for SAMER test).")
    args = p.parse_args()

    if not args.input.exists():
        sys.exit(f"Error: {args.input} not found.")

    rows = convert(args.input, args.format, args.prediction_column)

    if args.expected_rows is not None and len(rows) != args.expected_rows:
        sys.exit(f"Error: got {len(rows)} rows, expected {args.expected_rows}. Nothing written.")

    empty = sum(1 for r in rows if not r["source"])
    if empty:
        print(f"Warning: {empty} rows have an empty source.", file=sys.stderr)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    msg = f"Wrote {len(rows)} rows to {args.output}"
    if args.format == "samer":
        same = sum(1 for r in rows if r["references"][0] == r["source"])
        msg += f" | L5==L3 rows kept: {same} ({same / max(len(rows), 1):.1%})"
    print(msg)


if __name__ == "__main__":
    main()