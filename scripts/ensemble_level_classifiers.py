"""Combine CAMeLBERT-mix, AraBERT, and MARBERT's held-out predictions via majority vote.

No GPU needed -- this just joins the three already-saved per-example prediction parquets
(same 800-sentence held-out test set for all three, confirmed by identical schemas) and
computes a majority-vote ensemble prediction per sentence, then reports the same
exact/off-by-1/band accuracy metrics used throughout this project's level-classifier work.

Individual results going in:
  - CAMeLBERT-mix: 83.5% band (data/processed/level_classifier_bert_eval_results.parquet)
  - AraBERT:       83.4% band (data/processed/level_classifier_bert_arabert_eval_results.parquet)
  - MARBERT:       86.8% band (data/processed/level_classifier_bert_marbert_eval_results.parquet)
    -- MARBERT alone is already the best result in this project by a real margin (+3pt over
    the previous best, well outside the ~1.3pt noise band), so the ensemble's job is to beat
    86.8%, not just the earlier 83.5-83.9% cluster.

Tie-break rule: with 3 voters, a majority (2+ agreeing) always exists on any binary question
(the band decision), but for the 4-way EXACT level a 3-way split (all different) is possible
-- ties are broken by MARBERT's own prediction, since it's the strongest individual model.

Usage:
    uv run python scripts/ensemble_level_classifiers.py
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import EASY_LEVEL_CEILING, PROJECT_ROOT  # noqa: E402

PATHS = {
    "camelbert_mix": PROJECT_ROOT / "data" / "processed" / "level_classifier_bert_eval_results.parquet",
    "arabert": PROJECT_ROOT / "data" / "processed" / "level_classifier_bert_arabert_eval_results.parquet",
    "marbert": PROJECT_ROOT / "data" / "processed" / "level_classifier_bert_marbert_eval_results.parquet",
}
TIEBREAK_MODEL = "marbert"


def majority_vote(row: dict) -> int:
    votes = [row["predicted_level_camelbert_mix"], row["predicted_level_arabert"], row["predicted_level_marbert"]]
    counts = Counter(votes)
    top_count = max(counts.values())
    winners = [level for level, c in counts.items() if c == top_count]
    if len(winners) == 1:
        return winners[0]
    return row[f"predicted_level_{TIEBREAK_MODEL}"]  # all-different 3-way tie -> defer to the strongest model


def summarize(name: str, true_level: pl.Series, predicted_level: pl.Series) -> None:
    exact = (true_level == predicted_level).mean()
    off_by_one = (true_level - predicted_level).abs().le(1).mean()
    band = ((true_level > EASY_LEVEL_CEILING) == (predicted_level > EASY_LEVEL_CEILING)).mean()
    print(f"  [{name}] exact: {exact:.1%}  |  off-by-1: {off_by_one:.1%}  |  easy/hard band: {band:.1%}")


def main() -> None:
    frames = {}
    for tag, path in PATHS.items():
        if not path.exists():
            raise RuntimeError(f"missing {path} -- train that model first.")
        frames[tag] = pl.read_parquet(path)
        print(f"loaded {tag}: {frames[tag].shape[0]} rows")

    # NOT joined on (text, true_level): the held-out set has 794 unique texts across 800 rows
    # (a handful of short generic titles like "الدرس الثاني" / "Lesson Two" repeat across
    # different chapters), so that key isn't unique and produces a many-to-many join blowup
    # (confirmed: 830 rows instead of 800 on a first attempt). All three files were built by
    # the exact same deterministic code path (same seed, same load_and_clean_barec() +
    # build_balanced_sample() calls) -- verified their row order is bit-identical across all
    # three -- so a plain positional join is the correct, safe choice here.
    base = frames["camelbert_mix"]
    for tag in ("arabert", "marbert"):
        other = frames[tag]
        assert base["text"].to_list() == other["text"].to_list(), (
            f"row order mismatch between camelbert_mix and {tag} -- positional join would silently corrupt results."
        )
        base = base.with_columns(other["predicted_level"].alias(f"__tmp_{tag}"))
    joined = base.select(
        "text",
        "true_level",
        pl.col("predicted_level").alias("predicted_level_camelbert_mix"),
        pl.col("__tmp_arabert").alias("predicted_level_arabert"),
        pl.col("__tmp_marbert").alias("predicted_level_marbert"),
    )
    print(f"\npositionally joined (row order verified identical): {joined.shape[0]} rows")

    print("\nIndividual models on the joined set:")
    for tag in PATHS:
        summarize(tag, joined["true_level"], joined[f"predicted_level_{tag}"])

    ensemble_preds = [majority_vote(row) for row in joined.iter_rows(named=True)]
    joined = joined.with_columns(pl.Series("predicted_level_ensemble", ensemble_preds))

    print("\nMajority-vote ensemble:")
    summarize("ensemble", joined["true_level"], joined["predicted_level_ensemble"])

    best_individual_band = max(
        ((joined["true_level"] > EASY_LEVEL_CEILING) == (joined[f"predicted_level_{tag}"] > EASY_LEVEL_CEILING)).mean()
        for tag in PATHS
    )
    ensemble_band = ((joined["true_level"] > EASY_LEVEL_CEILING) == (joined["predicted_level_ensemble"] > EASY_LEVEL_CEILING)).mean()
    print(f"\nbest individual model band accuracy: {best_individual_band:.1%}  |  ensemble: {ensemble_band:.1%}")

    out_path = PROJECT_ROOT / "data" / "processed" / "level_classifier_ensemble_eval_results.parquet"
    joined.write_parquet(out_path)
    print(f"saved joined + ensemble predictions to {out_path}")


if __name__ == "__main__":
    main()
