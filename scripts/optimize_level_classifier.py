"""Compile ClassifyReadabilityLevel against real BAREC ground-truth labels.

BAREC's level labels are the ground truth for exactly the task this
validator performs (classify a sentence into 1 of this pipeline's 4
readability levels). Unlike the equivalence check, no manual labeling is
needed here -- the corpus already supplies it, at whatever scale we want.

Samples 1,000 sentences, BALANCED across levels 1-4 (250/level -- a
deliberately even split, not proportional to the corpus's natural
frequency, so the classifier gets fair representation of every level
during compilation and evaluation; this is different on purpose from the
main pipeline's stratified-by-natural-frequency pilot sample).

Splits into a 200-sentence bootstrap candidate pool (50/level) and an
800-sentence held-out set (200/level), compiles ClassifyReadabilityLevel
with dspy.BootstrapFewShot against the candidate pool, evaluates accuracy
on the held-out set for both the raw (zero-shot) and compiled classifier
so the optimizer's actual effect is visible, and saves the compiled
program to scripts/compiled/level_classifier.json.

barec_simplification_pipeline.py loads this compiled classifier
automatically if it exists, falling back to the raw zero-shot signature
otherwise.

Usage:
    uv run python scripts/optimize_level_classifier.py

Needs DEEPSEEK_API_KEY (see .env.example). Makes real, costed API calls:
bootstrapping tries calls against the 200-sentence candidate pool until it
finds enough successes, then evaluation runs all 800 held-out sentences
through BOTH the raw and compiled classifier (1,600 calls) to report the
before/after accuracy. Not run automatically -- run it yourself when ready.
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
    EASY_LEVEL_CEILING,
    PROJECT_ROOT,
    ClassifyReadabilityLevel,
    load_and_clean_barec,
)

PER_LEVEL_TOTAL = 250  # 250 x 4 levels = 1,000 total
PER_LEVEL_TRAIN = 50  # 50 x 4 = 200 bootstrap candidate pool; remaining 800 = held-out valset
SEED = 42


def build_balanced_sample(df: pl.DataFrame, n_per_level: int, seed: int) -> pl.DataFrame:
    """Equal count per level, not proportional to natural frequency (see module docstring)."""
    return df.group_by("Readability_Level_5", maintain_order=True).map_groups(
        lambda g: g.sample(n=min(n_per_level, g.shape[0]), seed=seed)
    )


def to_examples(df: pl.DataFrame) -> list[dspy.Example]:
    return [
        dspy.Example(text=row["Sentence"], level=row["Readability_Level_5"]).with_inputs("text")
        for row in df.iter_rows(named=True)
    ]


def level_exact_match(example: dspy.Example, prediction, trace=None) -> bool:
    return int(prediction.level) == int(example.level)


def easy_band_match(example: dspy.Example, prediction, trace=None) -> bool:
    """Exact level match implies band match, but not the reverse -- this is a strictly
    looser bar than level_exact_match, matching what the pipeline actually gates on
    (EASY_LEVEL_CEILING), not BAREC's exact numbering."""
    return (int(prediction.level) <= EASY_LEVEL_CEILING) == (int(example.level) <= EASY_LEVEL_CEILING)


def evaluate(classifier: dspy.Module, valset: list[dspy.Example], label: str) -> pl.DataFrame:
    """Returns per-example predictions (not just an aggregate score), so every downstream
    metric (band accuracy, off-by-one accuracy, a future compile's comparison against this
    one) can be computed later by reading a saved file instead of re-spending API calls on
    sentences we've already paid to evaluate.
    """
    rows = []
    for ex in valset:
        try:
            pred = classifier(text=ex.text)
            predicted_level = int(pred.level)
            failed = False
        except Exception as e:
            # A single truncated/malformed LM response shouldn't invalidate an accuracy run
            # that's already spent real API calls on everything before it -- log and move on.
            print(f"  skipped example: {type(e).__name__}: {str(e)[:150]}")
            predicted_level = None
            failed = True
        rows.append(
            {
                "classifier": label,
                "text": ex.text,
                "true_level": int(ex.level),
                "predicted_level": predicted_level,
                "failed": failed,
            }
        )
    return pl.DataFrame(rows)


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and fill it in."
        )

    print("Loading BAREC and building a balanced 1,000-sentence sample (250/level)...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)

    train_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    val_df = balanced.join(train_df, on="ID", how="anti")

    # build_balanced_sample groups by level, so train_df's row order is BLOCKED by level
    # (all level-1 rows, then all level-2, ...) -- confirmed directly, first 10 rows were
    # all level 1. BootstrapFewShot scans trainset in order and stops at max_bootstrapped_demos
    # successes, so an unshuffled trainset would hand it 4 level-1-only demos and never even
    # look at levels 2-4. Shuffle before compiling so demo selection sees a representative mix.
    train_df = train_df.sample(fraction=1.0, shuffle=True, seed=SEED)

    trainset = to_examples(train_df)
    valset = to_examples(val_df)
    print(f"trainset (bootstrap candidate pool): {len(trainset)} | valset (held-out): {len(valset)}")
    print(f"trainset levels, shuffled order (first 10): {[ex.level for ex in trainset[:10]]}")

    print("\nConfiguring DSPy (DeepSeek V4.1 Flash, temperature 0)...")
    # thinking={"type": "disabled"} + use_json_adapter_fallback=False: see the matching comments
    # in barec_simplification_pipeline.py's configure_dspy() -- both confirmed against the real
    # API as fixes for near-total call failure (thinking-mode output ate the whole token budget;
    # the JSON-mode fallback DSPy tries on any parse failure sends a param DeepSeek rejects).
    lm = dspy.LM(DEEPSEEK_MODEL, api_key=api_key, temperature=0.0, max_tokens=1024, thinking={"type": "disabled"})
    dspy.configure(lm=lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))

    raw_classifier = dspy.ChainOfThought(ClassifyReadabilityLevel)
    raw_classifier.set_lm(lm)

    def band_accuracy(results: pl.DataFrame) -> float:
        ok = results.filter(~pl.col("failed"))
        band = ok.filter(
            (pl.col("true_level") <= EASY_LEVEL_CEILING) == (pl.col("predicted_level") <= EASY_LEVEL_CEILING)
        ).shape[0]
        return band / ok.shape[0]

    def summarize(name: str, results: pl.DataFrame) -> None:
        ok = results.filter(~pl.col("failed"))
        n = ok.shape[0]
        exact = ok.filter(pl.col("true_level") == pl.col("predicted_level")).shape[0]
        adjacent = ok.filter((pl.col("true_level") - pl.col("predicted_level")).abs() <= 1).shape[0]
        print(
            f"  [{name}] exact: {exact / n:.1%}  |  off-by-1: {adjacent / n:.1%}  |  "
            f"easy/hard band: {band_accuracy(results):.1%}  ({n} scored, "
            f"{results.shape[0] - n} failed)"
        )

    print(f"\nEvaluating the raw (zero-shot) classifier on {len(valset)} held-out sentences...")
    raw_results = evaluate(raw_classifier, valset, "raw")
    summarize("raw", raw_results)

    print(f"\nBootstrapping against level_exact_match (strict) from the shuffled {len(trainset)}-sentence pool...")
    exact_optimizer = dspy.BootstrapFewShot(metric=level_exact_match, max_bootstrapped_demos=4, max_labeled_demos=8)
    compiled_exact = exact_optimizer.compile(raw_classifier, trainset=trainset)
    print(f"  demo levels used: {[d.get('level') for d in compiled_exact.predict.demos]}")

    print(f"\nEvaluating the exact-match-compiled classifier on the same {len(valset)} sentences...")
    compiled_exact_results = evaluate(compiled_exact, valset, "compiled_exact")
    summarize("compiled_exact", compiled_exact_results)

    print(f"\nBootstrapping against easy_band_match (loose) from the same shuffled pool...")
    band_optimizer = dspy.BootstrapFewShot(metric=easy_band_match, max_bootstrapped_demos=4, max_labeled_demos=8)
    compiled_band = band_optimizer.compile(raw_classifier, trainset=trainset)
    print(f"  demo levels used: {[d.get('level') for d in compiled_band.predict.demos]}")

    print(f"\nEvaluating the band-compiled classifier on the same {len(valset)} sentences...")
    compiled_band_results = evaluate(compiled_band, valset, "compiled_band")
    summarize("compiled_band", compiled_band_results)

    all_results = pl.concat([raw_results, compiled_exact_results, compiled_band_results])
    results_path = PROJECT_ROOT / "data" / "processed" / "level_classifier_eval_results.parquet"
    results_path.parent.mkdir(parents=True, exist_ok=True)
    all_results.write_parquet(results_path)
    print(f"\nsaved per-example predictions (raw + both compiled variants) to {results_path}")

    candidates = {
        "compiled_exact": (compiled_exact, compiled_exact_results),
        "compiled_band": (compiled_band, compiled_band_results),
    }
    best_name = max(candidates, key=lambda k: band_accuracy(candidates[k][1]))
    best_classifier, _ = candidates[best_name]
    print(f"\nSaving '{best_name}' as the production classifier (higher easy/hard band accuracy).")

    COMPILED_LEVEL_CLASSIFIER_PATH.parent.mkdir(parents=True, exist_ok=True)
    best_classifier.save(str(COMPILED_LEVEL_CLASSIFIER_PATH))
    print(f"saved compiled classifier to {COMPILED_LEVEL_CLASSIFIER_PATH}")


if __name__ == "__main__":
    main()
