"""One canonical source of truth for every count in docs/synthetic_data_card_v0_provisional.md's
waterfall table. Run this instead of hand-recomputing subsets of the pipeline -- prior review rounds
disagreed on short-source and duplicate-text counts because each side counted from a different stage
or with a different definition (e.g. word-tokenization choice, or the 13,470 pre-exclusion pool vs.
the 13,072 published export). This script states its definitions inline and computes every stage
from the actual committed/gitignored artifacts, not from memory of a prior run.

Usage: uv run python scripts/check_export_counts.py
"""
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_provenance import annotate_barec_provenance, filter_barec
from check_leakage import normalize as normalize_text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT = PROJECT_ROOT / "data" / "processed" / "barec_hard_pilot_checkpoint.jsonl"
PROVISIONAL = PROJECT_ROOT / "data" / "processed" / "barec_simplification_provisional.parquet"
SHORT_SOURCE_MAX_WORDS = 3  # matches the review's ">=" wording -- <=3 whitespace-split tokens


def main() -> None:
    # Plain json.loads, not pl.read_ndjson: some rows carry a NaN literal (invalid strict JSON,
    # inside the nested all_candidates field, which we don't need here) that polars' parser rejects
    # outright but Python's stdlib tolerates.
    rows = []
    with open(CHECKPOINT) as f:
        for line in f:
            d = json.loads(line)
            rows.append({"acceptance_tier": d["acceptance_tier"], "readability_lead": d["readability_lead"]})
    checkpoint = pl.DataFrame(rows)
    n_checkpoint = checkpoint.shape[0]
    tier_counts = checkpoint["acceptance_tier"].value_counts().to_dicts()
    tier = {r["acceptance_tier"]: r["count"] for r in tier_counts}
    n_c = tier.get("C", 0)
    n_ab = n_checkpoint - n_c
    n_quarantine = checkpoint.filter(
        (pl.col("acceptance_tier") != "C") & (pl.col("readability_lead") <= 0)
    ).shape[0]
    n_clean = n_ab - n_quarantine

    provisional = pl.read_parquet(PROVISIONAL)
    n_provisional = provisional.shape[0]
    provisional_by_type = provisional["pair_type"].value_counts().sort("pair_type").to_dicts()

    excluded = filter_barec(provisional, include=("train", "dev"), on_conflict="exclude")
    n_final = excluded.shape[0]
    n_excluded = n_provisional - n_final
    final_by_type = excluded["pair_type"].value_counts().sort("pair_type").to_dicts()

    print("=== waterfall: generation checkpoint -> published export ===")
    print(f"{n_checkpoint:>7,}  generation checkpoint (one winning candidate per hard-band source)")
    print(f"{-n_c:>7,}  tier C (rejected: fails equivalence gate, readability gate, or both)")
    print(f"{n_ab:>7,}  = tier A + B")
    print(f"{-n_quarantine:>7,}  quarantined (binary gate passes, but readability_lead <= 0)")
    print(f"{n_clean:>7,}  = clean generated pairs")
    for row in provisional_by_type:
        if row["pair_type"] != "generated":
            print(f"{row['count']:>+7,}  {row['pair_type']} pairs")
    print(f"{n_provisional:>7,}  = provisional pool (pre-BAREC-test-exclusion)")
    print(f"{-n_excluded:>7,}  BAREC-test-sourced rows excluded (annotate_barec_provenance + filter_barec)")
    print(f"{n_final:>7,}  = published export")
    print()
    print("published export by pair_type:")
    for row in final_by_type:
        print(f"  {row['pair_type']:<10} {row['count']:>7,}")

    print()
    print(f"=== short-source GENERATED pairs (source text <= {SHORT_SOURCE_MAX_WORDS} whitespace-split "
          "words) ===")
    # Scoped to pair_type == "generated": identity/scripture sources are short by construction
    # (identity is AoA-selected from the easy band, scripture is often single short verses), so
    # including them inflates the count without saying anything about the generation pipeline.
    generated = excluded.filter(pl.col("pair_type") == "generated")
    n_short = generated.filter(
        pl.col("original_text").str.split(" ").list.len() <= SHORT_SOURCE_MAX_WORDS
    ).shape[0]
    print(f"{n_short:,} of {generated.shape[0]:,} generated rows")

    print()
    print("=== duplicate source texts within the published export ===")
    excluded = excluded.with_columns(
        pl.col("original_text").map_elements(normalize_text, return_dtype=pl.Utf8).alias("_norm")
    )
    dup_groups = excluded.group_by("_norm").agg(pl.len().alias("n")).filter(pl.col("n") > 1)
    print(f"{dup_groups.shape[0]:,} distinct source texts appear more than once in the export")
    print(f"({dup_groups['n'].sum() - dup_groups.shape[0]:,} redundant rows if collapsed to one per text)")

    provenance = annotate_barec_provenance(excluded)
    n_cross = provenance.filter(pl.col("is_duplicate_across_splits")).shape[0]
    print(f"{n_cross:,} published rows whose source text also appears in a different BAREC split")


if __name__ == "__main__":
    main()
