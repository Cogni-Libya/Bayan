"""Compile ClassifyReadabilityLevel with MIPROv2 instead of BootstrapFewShot.

optimize_level_classifier.py's BootstrapFewShot passes only select few-shot demos --
the instructions in ClassifyReadabilityLevel's docstring/field descriptions were
hand-written once and never actually tuned against anything. That was fine as a first
sanity-check pass (get BAREC ground truth wired up, confirm the pipeline works at
all), but MIPROv2 searches instructions AND demos jointly, so it's worth trying now
that there's a real baseline to beat: compiled_band reached 79.7% easy/hard band
accuracy, 53.0% exact, only 7/800 failures (see
data/processed/level_classifier_eval_results.parquet).

Unlike the equivalence validator, this needs no human annotation -- BAREC's level
labels are ground truth for exactly this task, at whatever scale we want. Reuses the
SAME balanced sample (same PER_LEVEL_TOTAL/PER_LEVEL_TRAIN/SEED as
optimize_level_classifier.py) so the 800-sentence held-out band accuracy is directly
comparable to the existing recorded number, not a different split.

Optimizes against easy_band_match only, not level_exact_match: the earlier
BootstrapFewShot run showed the band-aware metric produced far fewer catastrophic
failures (7 vs 32) and better numbers across the board than optimizing for exact
level match, and band match is what the pipeline actually gates simplification output
on (EASY_LEVEL_CEILING) -- no reason to spend budget re-litigating that.

Only overwrites the production classifier (scripts/compiled/level_classifier.json) if
the MIPROv2-compiled version actually beats the existing BootstrapFewShot one on
held-out band accuracy, read back from the already-saved eval results parquet rather
than re-spending calls to re-measure it.

Usage:
    uv run python scripts/optimize_level_classifier_mipro.py

Needs DEEPSEEK_API_KEY. Real costed API calls: MIPROv2 auto="light" internally caps
its search valset to 100 sentences (minibatches of 35 most trials, full 100 every 5th
trial) across ~10 trials, plus bootstrap/instruction-proposal overhead -- then this
script does its own full 800-sentence evaluate() pass on the compiled result for a
fair comparison against the existing number. Roughly 1,400-1,600 calls total, on the
order of a few dollars at DeepSeek Flash pricing (~3x optimize_equivalence_validator.py's
run, since that one's held-out set is 16 sentences vs. this one's 800). Not run
automatically -- run it yourself when ready.
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
from optimize_level_classifier import (  # noqa: E402
    PER_LEVEL_TOTAL,
    PER_LEVEL_TRAIN,
    SEED,
    build_balanced_sample,
    easy_band_match,
    evaluate,
    level_exact_match,
    to_examples,
)

PREVIOUS_RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "level_classifier_eval_results.parquet"
MIPRO_RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "level_classifier_mipro_eval_results.parquet"


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
        f"easy/hard band: {band_accuracy(results):.1%}  ({n} scored, {results.shape[0] - n} failed)"
    )


def main() -> None:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and fill it in."
        )

    if not PREVIOUS_RESULTS_PATH.exists():
        raise RuntimeError(
            f"{PREVIOUS_RESULTS_PATH} not found -- run optimize_level_classifier.py first, "
            "this script compares against its saved compiled_band results."
        )
    previous = pl.read_parquet(PREVIOUS_RESULTS_PATH)
    previous_band = previous.filter(pl.col("classifier") == "compiled_band")
    if previous_band.shape[0] == 0:
        raise RuntimeError(f"no 'compiled_band' rows in {PREVIOUS_RESULTS_PATH} -- can't compare against it.")
    baseline_band_acc = band_accuracy(previous_band)
    print(f"Existing BootstrapFewShot compiled_band baseline (read from saved results, no new calls):")
    summarize("compiled_band (existing)", previous_band)

    print("\nRebuilding the SAME balanced sample as optimize_level_classifier.py (same seed)...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)
    train_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    val_df = balanced.join(train_df, on="ID", how="anti")
    train_df = train_df.sample(fraction=1.0, shuffle=True, seed=SEED)

    trainset = to_examples(train_df)
    valset = to_examples(val_df)
    assert len(valset) == previous_band.shape[0], (
        f"valset size {len(valset)} doesn't match the saved baseline's {previous_band.shape[0]} rows -- "
        "the sample isn't reproducing the same split, comparison would be unfair. Stopping."
    )
    print(f"trainset: {len(trainset)} | valset (held-out, matches baseline row count): {len(valset)}")

    print("\nConfiguring DSPy (DeepSeek V4.1 Flash, temperature 0)...")
    lm = dspy.LM(
        DEEPSEEK_MODEL,
        api_key=api_key,
        temperature=0.0,
        max_tokens=1024,
        thinking={"type": "disabled"},
        timeout=90,
    )
    dspy.configure(lm=lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))

    raw_classifier = dspy.ChainOfThought(ClassifyReadabilityLevel)
    raw_classifier.set_lm(lm)

    print("\nRunning MIPROv2 (auto='light', metric=easy_band_match) -- optimizes instructions AND demos jointly...")
    optimizer = dspy.MIPROv2(metric=easy_band_match, auto="light", seed=SEED)
    compiled_mipro = optimizer.compile(raw_classifier, trainset=trainset, valset=valset)

    print(f"\nEvaluating the MIPROv2-compiled classifier on the full {len(valset)}-sentence held-out set...")
    mipro_results = evaluate(compiled_mipro, valset, "compiled_mipro")
    summarize("compiled_mipro", mipro_results)

    MIPRO_RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    mipro_results.write_parquet(MIPRO_RESULTS_PATH)
    print(f"\nsaved per-example predictions to {MIPRO_RESULTS_PATH}")

    mipro_band_acc = band_accuracy(mipro_results)
    print(f"\nband accuracy -- existing compiled_band: {baseline_band_acc:.1%}  |  new compiled_mipro: {mipro_band_acc:.1%}")
    if mipro_band_acc > baseline_band_acc:
        COMPILED_LEVEL_CLASSIFIER_PATH.parent.mkdir(parents=True, exist_ok=True)
        compiled_mipro.save(str(COMPILED_LEVEL_CLASSIFIER_PATH))
        print(f"MIPROv2 wins -- saved as the new production classifier at {COMPILED_LEVEL_CLASSIFIER_PATH}")
    else:
        print("MIPROv2 did not beat the existing BootstrapFewShot classifier -- production classifier left unchanged.")


if __name__ == "__main__":
    main()
