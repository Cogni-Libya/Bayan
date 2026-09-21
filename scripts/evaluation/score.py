"""
Scoring script for Bayan simplification models.

Usage:
    uv run python scripts/evaluation/score.py <predictions.jsonl>

Input format: one JSON object per line, with fields:
    id            - unique row id
    source        - the original (complex) sentence
    prediction    - the model's simplified output
    references    - list of gold simplifications (may be empty, e.g. for BAREC)
"""
import json
import logging
import re
import sys

import evaluate
import sacrebleu
import torch
from bert_score import score as bertscore_score
from transformers import AutoModelForSequenceClassification, AutoTokenizer

logging.getLogger("transformers").setLevel(logging.ERROR)

# ---------------------------------------------------------------------------
# Models (loaded once at import time)
# ---------------------------------------------------------------------------

SARI_IMPLEMENTATION = "huggingface/evaluate (sari, wraps EASSE-style SARI)"
_sari_metric = evaluate.load("sari")

READABILITY_MODEL_NAME = "CAMeL-Lab/readability-arabertv02-word-CE"
_readability_tokenizer = AutoTokenizer.from_pretrained(READABILITY_MODEL_NAME)
_readability_model = AutoModelForSequenceClassification.from_pretrained(READABILITY_MODEL_NAME)
_readability_model.eval()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Row-level helpers
# ---------------------------------------------------------------------------

_ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED\u08D4-\u08E1\u08E3-\u08FF]"
)


def strip_diacritics(text: str) -> str:
    """Remove Arabic diacritics (tashkeel) — the readability model is more
    reliable on undiacritized text, per the task spec."""
    return _ARABIC_DIACRITICS.sub("", text)


CHANGED = "Changed references"
UNCHANGED = "Unchanged references"
NO_REFERENCE = "No references"


def reference_status(row: dict) -> str:
    """Which bucket a row belongs in.

    A row with no references is NOT 'unchanged'. 'Unchanged' means the human
    reference left this sentence alone, so a good model should leave it alone too —
    a claim we cannot make without a reference. BAREC has no reference
    simplifications at all, so its rows get their own bucket and only the metrics
    that don't need references.
    """
    if not row["references"]:
        return NO_REFERENCE
    source = row["source"].strip()
    return CHANGED if any(ref.strip() != source for ref in row["references"]) else UNCHANGED


def split_by_reference(rows: list[dict]) -> dict[str, list[dict]]:
    """Group rows into the three buckets, keeping empty ones so the report is stable."""
    buckets: dict[str, list[dict]] = {CHANGED: [], UNCHANGED: [], NO_REFERENCE: []}
    for row in rows:
        buckets[reference_status(row)].append(row)
    return buckets


def make_copy_baseline(rows: list[dict]) -> list[dict]:
    """The 'model that does nothing': prediction replaced with source.
    Every real model must beat this."""
    return [{**r, "prediction": r["source"]} for r in rows]


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def copy_rate(rows: list[dict]) -> float:
    """Share of predictions identical to their source — i.e. the model did nothing."""
    if not rows:
        return 0.0
    copied = sum(1 for r in rows if r["prediction"].strip() == r["source"].strip())
    return copied / len(rows)


def compute_sari(rows: list[dict]) -> float:
    """
    Average SARI over rows that HAVE references.
    SARI needs: source, prediction, and >=1 reference per row.
    Rows with no references (e.g. BAREC) are skipped — caller must check for this.
    """
    scorable = [r for r in rows if r["references"]]
    if not scorable:
        return float("nan")

    result = _sari_metric.compute(
        sources=[r["source"] for r in scorable],
        predictions=[r["prediction"] for r in scorable],
        references=[r["references"] for r in scorable],
    )
    return result["sari"]


def compute_bleu(rows: list[dict]) -> float:
    """Average BLEU over rows that HAVE references."""
    scorable = [r for r in rows if r["references"]]
    if not scorable:
        return float("nan")

    predictions = [r["prediction"] for r in scorable]
    # sacrebleu wants references transposed: list of lists, one per reference position
    max_refs = max(len(r["references"]) for r in scorable)
    references_transposed = [
        [r["references"][i] if i < len(r["references"]) else "" for r in scorable]
        for i in range(max_refs)
    ]

    result = sacrebleu.corpus_bleu(predictions, references_transposed)
    return result.score


def compute_bertscore(rows: list[dict]) -> float:
    """
    Meaning preservation: BERTScore F1 between source and prediction.
    Doesn't need references — works on every row, including BAREC.
    """
    if not rows:
        return float("nan")

    _, _, f1 = bertscore_score(
        [r["prediction"] for r in rows],
        [r["source"] for r in rows],
        lang="ar",
        verbose=False,
    )
    return f1.mean().item()


def predict_readability_level(text: str) -> float:
    """Predict a sentence's reading level on BAREC's 19-level scale.
    Text is undiacritized first (model is more reliable that way).
    Returns the expected level: softmax-weighted average over the 19 classes,
    since this is a 19-way classifier, not a regressor."""
    text = strip_diacritics(text)
    inputs = _readability_tokenizer(text, return_tensors="pt", truncation=True)
    with torch.no_grad():
        outputs = _readability_model(**inputs)

    probs = torch.softmax(outputs.logits.squeeze(), dim=0)
    levels = torch.arange(1, len(probs) + 1, dtype=torch.float)
    return (probs * levels).sum().item()


def compute_readability_drop(rows: list[dict]) -> float:
    """Average (source level - prediction level). Positive = got easier."""
    if not rows:
        return float("nan")
    drops = [
        predict_readability_level(r["source"]) - predict_readability_level(r["prediction"])
        for r in rows
    ]
    return sum(drops) / len(drops)


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(rows: list[dict], label: str) -> None:
    """Print all metrics for one set of rows, one section."""
    print(f"\n--- {label} (n={len(rows)}) ---")
    if not rows:
        print("(no rows)")
        return
    print(f"Copy rate:        {copy_rate(rows):.3f}")
    if any(r["references"] for r in rows):
        print(f"SARI:             {compute_sari(rows):.3f}")
        print(f"BLEU:             {compute_bleu(rows):.3f}")
    else:
        print("SARI, BLEU:       not scored (no reference simplifications)")
    print(f"BERTScore:        {compute_bertscore(rows):.3f}")
    print(f"Readability drop: {compute_readability_drop(rows):.3f}")


def main(path: str) -> None:
    rows = load_jsonl(path)
    buckets = split_by_reference(rows)

    print(f"SARI implementation: {SARI_IMPLEMENTATION}")
    counts = ", ".join(f"{len(v)} {k.lower()}" for k, v in buckets.items())
    print(f"Loaded {len(rows)} rows ({counts})")

    for heading, scored_rows in (
        ("MODEL", rows),
        ("COPY BASELINE", make_copy_baseline(rows)),
    ):
        print(f"\n========== {heading} ==========")
        report(scored_rows, "Overall")
        for label, bucket in split_by_reference(scored_rows).items():
            report(bucket, label)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: uv run python scripts/evaluation/score.py <predictions.jsonl>")
        sys.exit(1)
    main(sys.argv[1])