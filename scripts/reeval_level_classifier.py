"""Re-evaluate the currently-saved compiled level classifier with a larger max_tokens budget.

optimize_level_classifier_mipro.py's MIPROv2 run produced a classifier whose proposed
instructions push the model toward longer, more structured chain-of-thought reasoning
(walking through morphology/syntax/vocabulary/content before stating a level) than the
original hand-written instructions did. At max_tokens=1024, that reasoning sometimes ran
out of budget before the model reached the `level` field, causing an AdapterParseError --
16 of 800 held-out sentences failed this way (vs. 7/800 for the prior BootstrapFewShot
classifier), while the two classifiers' accuracy numbers were within noise of each other
(79.7% vs 80.2% band accuracy, n~790, SE~1.4pp).

This script does NOT re-run MIPROv2 -- the compiled program is already saved at
scripts/compiled/level_classifier.json. It just re-evaluates that SAME already-compiled
classifier against the SAME 800-sentence held-out split, with max_tokens raised, to check
whether the failures were a token-budget artifact rather than a real quality regression.

Usage:
    uv run python scripts/reeval_level_classifier.py

Needs DEEPSEEK_API_KEY. Real costed calls: up to 800 (one per held-out sentence), no
search/optimization involved.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dspy
import polars as pl
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import (  # noqa: E402
    COMPILED_LEVEL_CLASSIFIER_PATH,
    DEEPSEEK_MODEL,
    PROJECT_ROOT,
    ClassifyReadabilityLevel,
    load_and_clean_barec,
)
from optimize_level_classifier import (  # noqa: E402
    PER_LEVEL_TOTAL,
    PER_LEVEL_TRAIN,
    SEED,
    build_balanced_sample,
    evaluate,
    to_examples,
)
from optimize_level_classifier_mipro import band_accuracy, summarize  # noqa: E402

MAX_TOKENS = 2048  # up from 1024, to give the MIPROv2 classifier's longer reasoning room
RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "level_classifier_mipro_reeval_results.parquet"


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and fill it in."
        )

    if not COMPILED_LEVEL_CLASSIFIER_PATH.exists():
        raise RuntimeError(f"{COMPILED_LEVEL_CLASSIFIER_PATH} not found -- nothing to re-evaluate.")

    print("Rebuilding the SAME balanced sample as optimize_level_classifier.py (same seed)...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)
    train_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    val_df = balanced.join(train_df, on="ID", how="anti")
    valset = to_examples(val_df)
    print(f"valset (held-out): {len(valset)}")

    print(f"\nConfiguring DSPy (DeepSeek V4.1 Flash, temperature 0, max_tokens={MAX_TOKENS})...")
    lm = dspy.LM(
        DEEPSEEK_MODEL,
        api_key=api_key,
        temperature=0.0,
        max_tokens=MAX_TOKENS,
        thinking={"type": "disabled"},
        timeout=90,
    )
    dspy.configure(lm=lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))

    print(f"Loading the already-compiled MIPROv2 classifier from {COMPILED_LEVEL_CLASSIFIER_PATH}...")
    classifier = dspy.ChainOfThought(ClassifyReadabilityLevel)
    classifier.load(str(COMPILED_LEVEL_CLASSIFIER_PATH))
    classifier.set_lm(lm)

    print(f"\nEvaluating on the full {len(valset)}-sentence held-out set with the larger token budget...")
    results = evaluate(classifier, valset, "compiled_mipro_reeval")
    summarize("compiled_mipro_reeval", results)

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(RESULTS_PATH)
    print(f"\nsaved per-example predictions to {RESULTS_PATH}")

    print(f"\nband accuracy -- previous run (max_tokens=1024, 16 failed): 80.2%  |  this run (max_tokens={MAX_TOKENS}): {band_accuracy(results):.1%}")
    print("Compare failure counts above against the previous run's 16/800 to see if raising max_tokens fixed the truncations.")


if __name__ == "__main__":
    main()
