"""Compile CheckSemanticEquivalence (batched signature) against human-annotated ground truth.

CheckSemanticEquivalence now scores a LIST of candidate simplifications against one original
in a single call (simplified_candidates -> equivalence_scores, plus reasoning_per_candidate),
not one candidate per call -- see the signature's own docstring in barec_simplification_pipeline.py
for why (the reranking redesign: NUM_CANDIDATES=5 candidates generated and scored per hard
sentence, in 2 API calls total instead of NUM_CANDIDATES*3). That signature change invalidated
the previous compiled validator (archived to scripts/compiled/archive/), which is why this
script exists again -- same annotation data, same MIPROv2 approach, adapted I/O shape.

KNOWN LIMITATION, stated plainly: our annotation data (from the Pilot Pair Review artifact) is
one human verdict per (original, single candidate) pair -- collected back when the pipeline
only ever generated one candidate per sentence. We have no real "5 candidates judged together"
ground truth. This script adapts by training/evaluating on BATCH-OF-1 calls: each example's
simplified_candidates list has exactly one item, and reasoning_per_candidate isn't scored
against anything (no annotated reasoning text exists to compare against -- only the resulting
equivalence_scores[0] is checked against the human verdict). This is the most honest evaluation
available given the data that exists; real production calls batch 5 candidates together, which
could behave somewhat differently (the signature explicitly warns the model not to let one
candidate's judgment anchor another's, but that's an instruction, not a guarantee). Revisit if/
when annotation data naturally includes multi-candidate batches.

Reads data/annotations/equivalence_and_level_annotations.json (a snapshot pulled from the
artifact's shared database -- not live; re-pull and re-save that file for a fresher run) and
data/processed/barec_hard_pilot_raw_results.parquet, joins them by ID, and reconstructs the
TRUE target per annotated row:
  - "ok"                       -> target = 1.0 if the pipeline's original equivalent flag
                                   was True, else 0.0 (confirms whatever it originally said)
  - "should_be_equivalent"     -> target = 1.0 (overrides a wrong low/False verdict)
  - "should_not_be_equivalent" -> target = 0.0 (overrides a wrong high/True verdict)
Rows with no equiv_verdict (level-only corrections, notes-only, cleared) are excluded -- this
is real ground truth, not an assumption filled in for rows nobody actually judged.

Uses MIPROv2 with auto="light": it searches BOTH instruction phrasing and few-shot demos,
which matters here because this signature's instructions have never been tuned against
anything under its new batched shape.

Usage:
    uv run python scripts/optimize_equivalence_validator.py

Needs DEEPSEEK_API_KEY (see .env.example). Makes real, costed API calls: a light MIPROv2 run
is roughly 200-300 calls (6 candidate proposals, ~10 trials, each scored against the held-out
split). NOT run automatically, and NOT run as part of preparing this script -- the script has
been written and validated (imports, data loading, dry structure) but deliberately not executed
against the real API yet. Run it yourself when ready.
"""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import numpy as np
import onnxruntime  # noqa: F401 -- import before dspy; see barec_simplification_pipeline.py's
# import-order comment for why (dspy's lazy-import machinery corrupts numpy's C-core init if
# dspy loads first, which then breaks onnxruntime's own numpy dependency). Not used directly in
# this script, but importing barec_simplification_pipeline triggers its numpy/onnxruntime
# imports anyway -- doing it here first, before dspy, keeps that fix in effect for this script too.
import dspy
import polars as pl
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import (  # noqa: E402
    DEEPSEEK_MODEL,
    PROJECT_ROOT,
    CheckSemanticEquivalence,
)

ANNOTATIONS_PATH = PROJECT_ROOT / "data" / "annotations" / "equivalence_and_level_annotations.json"
RAW_RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "barec_hard_pilot_raw_results.parquet"
COMPILED_PATH = PROJECT_ROOT / "scripts" / "compiled" / "equivalence_validator.json"

VAL_FRACTION = 0.25
SEED = 42
DECISION_THRESHOLD = 0.5  # only for reporting a thresholded-accuracy figure comparable to
# earlier documented numbers -- NOT the same as the pipeline's own EQUIVALENCE_THRESHOLD=0.7,
# which is a separate, calibrated, more conservative production decision.


def load_examples() -> list[dspy.Example]:
    annotations = json.loads(ANNOTATIONS_PATH.read_text(encoding="utf-8"))
    raw = pl.read_parquet(RAW_RESULTS_PATH)

    examples = []
    for a in annotations:
        verdict = a.get("equiv_verdict")
        if not verdict:
            continue  # level-only correction, note-only, or cleared -- no equivalence judgment
        row = raw.filter(pl.col("ID") == int(a["id"]))
        if row.shape[0] == 0:
            continue  # annotated ID not found in this results snapshot -- skip rather than guess
        row = row.row(0, named=True)

        if verdict == "ok":
            target = 1.0 if bool(row["equivalent"]) else 0.0
        elif verdict == "should_be_equivalent":
            target = 1.0
        elif verdict == "should_not_be_equivalent":
            target = 0.0
        else:
            continue

        # Batch-of-1: see module docstring's KNOWN LIMITATION for why.
        examples.append(
            dspy.Example(
                original_text=row["original_text"],
                simplified_candidates=[row["simplified_text"]],
                equivalence_scores=[target],
            ).with_inputs("original_text", "simplified_candidates")
        )
    return examples


def equiv_score_metric(example: dspy.Example, prediction, trace=None) -> float:
    """Graded closeness metric: 1.0 when the predicted score exactly matches the 0.0/1.0
    target, degrading linearly with distance. Batch-of-1, so this compares index 0 of the
    target list against index 0 of whatever the model returned -- defensively checks the
    prediction actually has at least one score before indexing (a real new failure mode
    with list outputs: the model can return an empty or mismatched-length list)."""
    target = float(example.equivalence_scores[0])
    predicted_list = list(prediction.equivalence_scores)
    if not predicted_list:
        return 0.0  # nothing returned -- worst possible score, not a crash
    predicted = max(0.0, min(1.0, float(predicted_list[0])))
    return 1.0 - abs(target - predicted)


def evaluate(validator: dspy.Module, valset: list[dspy.Example], label: str) -> pl.DataFrame:
    rows = []
    for ex in valset:
        try:
            pred = validator(original_text=ex.original_text, simplified_candidates=ex.simplified_candidates)
            predicted_list = list(pred.equivalence_scores)
            predicted = max(0.0, min(1.0, float(predicted_list[0]))) if predicted_list else None
            failed = predicted is None
        except Exception as e:
            print(f"  skipped example: {type(e).__name__}: {str(e)[:150]}")
            predicted = None
            failed = True
        rows.append(
            {
                "classifier": label,
                "original_text": ex.original_text,
                "simplified_text": ex.simplified_candidates[0],
                "true_score": float(ex.equivalence_scores[0]),
                "predicted_score": predicted,
                "failed": failed,
            }
        )
    return pl.DataFrame(rows)


def summarize(name: str, results: pl.DataFrame) -> None:
    ok = results.filter(~pl.col("failed"))
    n = ok.shape[0]
    mean_closeness = ok.select((1 - (pl.col("true_score") - pl.col("predicted_score")).abs()).mean()).item()
    thresholded_correct = ok.filter(
        (pl.col("true_score") >= DECISION_THRESHOLD) == (pl.col("predicted_score") >= DECISION_THRESHOLD)
    ).shape[0]
    print(
        f"  [{name}] mean score closeness: {mean_closeness:.3f}  |  "
        f"thresholded accuracy (@{DECISION_THRESHOLD}): {thresholded_correct / n:.1%}  "
        f"({n} scored, {results.shape[0] - n} failed)"
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and fill it in."
        )

    print(f"Loading annotations from {ANNOTATIONS_PATH}...")
    examples = load_examples()
    n_true = sum(1 for e in examples if e.equivalence_scores[0] >= DECISION_THRESHOLD)
    print(f"usable examples: {len(examples)} ({n_true} equivalent / {len(examples) - n_true} not equivalent)")

    rng_order = list(examples)
    random.Random(SEED).shuffle(rng_order)
    n_val = max(1, int(len(rng_order) * VAL_FRACTION))
    valset = rng_order[:n_val]
    trainset = rng_order[n_val:]
    print(f"trainset: {len(trainset)} | valset (held-out): {len(valset)}")

    print("\nConfiguring DSPy (DeepSeek V4.1 Flash)...")
    # max_tokens=4096: matches barec_simplification_pipeline.py's judge_lm -- this signature
    # returns a reasoning string per candidate plus a score per candidate, more output per call
    # than the old single-pair signature was sized for, even at batch-of-1 here.
    lm = dspy.LM(DEEPSEEK_MODEL, api_key=api_key, temperature=0.0, max_tokens=4096, thinking={"type": "disabled"}, timeout=90)
    dspy.configure(lm=lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))

    # dspy.Predict, not ChainOfThought: CheckSemanticEquivalence declares its own
    # reasoning_per_candidate output field -- see barec_simplification_pipeline.py's
    # configure_dspy() comment for why ChainOfThought would be redundant here.
    raw_validator = dspy.Predict(CheckSemanticEquivalence)
    raw_validator.set_lm(lm)

    print(f"\nEvaluating the raw (zero-shot) validator on {len(valset)} held-out annotated pairs...")
    raw_results = evaluate(raw_validator, valset, "raw")
    summarize("raw", raw_results)

    print("\nRunning MIPROv2 (auto='light') -- optimizes instructions AND demos jointly...")
    optimizer = dspy.MIPROv2(metric=equiv_score_metric, auto="light", seed=SEED)
    compiled_validator = optimizer.compile(raw_validator, trainset=trainset, valset=valset)

    print(f"\nEvaluating the MIPROv2-compiled validator on the same {len(valset)} pairs...")
    compiled_results = evaluate(compiled_validator, valset, "compiled_mipro")
    summarize("compiled_mipro", compiled_results)

    all_results = pl.concat([raw_results, compiled_results])
    results_path = PROJECT_ROOT / "data" / "processed" / "equivalence_validator_eval_results.parquet"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    all_results.write_parquet(results_path)
    print(f"\nsaved per-example predictions (raw + compiled) to {results_path}")

    COMPILED_PATH.parent.mkdir(parents=True, exist_ok=True)
    compiled_validator.save(str(COMPILED_PATH))
    print(f"saved compiled validator to {COMPILED_PATH}")


if __name__ == "__main__":
    main()
