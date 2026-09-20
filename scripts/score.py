"""
Scoring script for Bayan simplification models.
Usage: uv run python scripts/score.py <predictions.jsonl>
"""
import json
import sys
import evaluate

def load_jsonl(path: str) -> list[dict]:
    """Load predictions. Each line: id, source, prediction, references (list, may be empty)."""
    rows = []
    with open(path, encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for key in ("id", "source", "prediction"):
                if key not in row:
                    raise ValueError(f"{path}:{line_num} missing required field '{key}'")
            row.setdefault("references", [])
            rows.append(row)
    return rows


def copy_rate(rows: list[dict]) -> float:
    """Share of predictions identical to their source — i.e. the model did nothing."""
    if not rows:
        return 0.0
    copied = sum(1 for r in rows if r["prediction"].strip() == r["source"].strip())
    return copied / len(rows)


SARI_IMPLEMENTATION = "huggingface/evaluate (sari, wraps EASSE-style SARI)"
_sari_metric = evaluate.load("sari")


def compute_sari(rows: list[dict]) -> float:
    """
    Average SARI over rows that HAVE references.
    SARI needs: source, prediction, and >=1 reference per row.
    Rows with no references (e.g. BAREC) are skipped — caller must check for this.
    """
    scorable = [r for r in rows if r["references"]]
    if not scorable:
        return float("nan")

    sources = [r["source"] for r in scorable]
    predictions = [r["prediction"] for r in scorable]
    references = [r["references"] for r in scorable]

    result = _sari_metric.compute(
        sources=sources,
        predictions=predictions,
        references=references,
    )
    return result["sari"]


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/score.py <predictions.jsonl>")
        sys.exit(1)

    rows = load_jsonl(sys.argv[1])
    print(f"SARI implementation: {SARI_IMPLEMENTATION}")
    print(f"Loaded {len(rows)} rows")
    print(f"Copy rate: {copy_rate(rows):.3f}")
    print(f"SARI: {compute_sari(rows):.3f}")