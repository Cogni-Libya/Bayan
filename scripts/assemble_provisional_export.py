"""Assemble the provisional training-ready dataset from the hard-band checkpoint:
  - generated (hard-band): tier A+B, quarantine (readability_lead<=0) excluded.
  - identity (easy-band no-op): a small (~5%) fraction selected by lowest mean AoA -- not by BAREC
    level, which is only the floor/pool -- domain- and length-matched to the generated set so
    "easy" doesn't collapse to "short news headline."
  - scripture: a small natural sample, preserved verbatim regardless of assessed difficulty.

All local, no API calls. Quarantined rows are saved separately, not discarded, for later review.

Usage: uv run python scripts/assemble_provisional_export.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import (
    EASY_LEVEL_CEILING, EASY_LEVELS, build_identity_pairs, load_and_clean_barec,
)
from lexical_scorer import LexicalScorer

SCRIPTURE_SOURCES = {"Quran", "Hadith", "Old Testament", "New Testament"}  # v0's set; v1 is assemble_corpus_v1.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CHECKPOINT_PATH = PROJECT_ROOT / "data" / "processed" / "barec_hard_pilot_checkpoint.jsonl"
QUARANTINE_PATH = PROJECT_ROOT / "data" / "processed" / "barec_hard_pilot_quarantine_lead_le0.jsonl"
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "barec_simplification_provisional.parquet"

TIER_A_EQ = 0.85
N_IDENTITY = 600
N_SCRIPTURE = 100
N_LENGTH_BINS = 5


def tier_of(row: dict) -> str:
    if row.get("acceptance_tier"):
        return row["acceptance_tier"]
    if not (row["equivalent"] and row["readability_passed"]):
        return "C"
    return "A" if row["equivalence_score"] >= TIER_A_EQ else "B"


def load_generated_pairs() -> pl.DataFrame:
    rows = []
    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    for r in rows:
        r["_tier"] = tier_of(r)

    ab = [r for r in rows if r["_tier"] in ("A", "B")]
    quarantine = [r for r in ab if r["readability_lead"] <= 0]
    clean = [r for r in ab if r["readability_lead"] > 0]
    print(f"generated (hard): {len(clean)} clean "
          f"(A={sum(1 for r in clean if r['_tier'] == 'A')}, B={sum(1 for r in clean if r['_tier'] == 'B')}), "
          f"{len(quarantine)} quarantined (lead<=0)")

    QUARANTINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(QUARANTINE_PATH, "w", encoding="utf-8") as f:
        for r in quarantine:
            r.pop("_tier", None)
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    return pl.DataFrame(infer_schema_length=None, data=[
        {
            "ID": r["ID"], "original_text": r["original_text"], "simplified_text": r["simplified_text"],
            "source_level": r["source_level"], "predicted_level": r["predicted_level"],
            "equivalent": r["equivalent"], "equivalence_reasoning": r["equivalence_reasoning"],
            "is_easy": r["is_easy"], "pair_type": "generated",
            "equivalence_score": r["equivalence_score"], "acceptance_tier": r["_tier"],
            "readability_lead": r["readability_lead"], "ease_score": r.get("ease_score"), "d_logit": r["d_logit"],
            "provisional": True,
        }
        for r in clean
    ])


def _diagnostic_null_columns() -> list[pl.Expr]:
    return [
        pl.lit(None, dtype=pl.Float64).alias("equivalence_score"),
        pl.lit(None, dtype=pl.Utf8).alias("acceptance_tier"),
        pl.lit(None, dtype=pl.Float64).alias("readability_lead"),
        pl.lit(None, dtype=pl.Float64).alias("ease_score"),
        pl.lit(None, dtype=pl.Float64).alias("d_logit"),
        pl.lit(True).alias("provisional"),
    ]


def load_identity_pairs(generated_df: pl.DataFrame, barec: pl.DataFrame) -> pl.DataFrame:
    is_scripture = pl.col("Source").is_in(SCRIPTURE_SOURCES)
    easy_pool = barec.filter(~is_scripture & pl.col("Readability_Level_5").is_in(EASY_LEVELS))
    print(f"easy-band candidate pool: {easy_pool.shape[0]}")

    lexical_scorer = LexicalScorer()
    easy_rows = easy_pool.to_dicts()
    for r in easy_rows:
        mean_aoa, _, _ = lexical_scorer.text(r["Sentence"])
        r["mean_aoa"] = mean_aoa

    gen_ids = set(generated_df["ID"].to_list())
    gen_meta = barec.filter(pl.col("ID").is_in(gen_ids)).select("ID", "Domain", "Word_Count")
    domain_counts = gen_meta["Domain"].value_counts().to_dicts()
    domain_frac = {d["Domain"]: d["count"] / gen_meta.shape[0] for d in domain_counts}

    # Length matching: quintile-bucket the generated set's word-count distribution, then draw
    # proportionally from the same buckets in the easy pool (lowest AoA within each bucket) -- a
    # loose min/max band alone still lets AoA-sorting collapse onto the shortest texts, since fewer
    # words trivially means lower mean AoA.
    gen_wc = gen_meta["Word_Count"].to_numpy()
    bin_edges = np.quantile(gen_wc, np.linspace(0, 1, N_LENGTH_BINS + 1))
    bin_edges[0], bin_edges[-1] = -np.inf, np.inf
    bin_frac = np.histogram(gen_wc, bins=bin_edges)[0] / len(gen_wc)

    identity_selected = []
    for domain, frac in domain_frac.items():
        target_n = round(N_IDENTITY * frac)
        domain_pool = [r for r in easy_rows if r["Domain"] == domain]
        wc_arr = np.array([r["Word_Count"] for r in domain_pool])
        bin_idx = np.digitize(wc_arr, bin_edges[1:-1])
        for b in range(N_LENGTH_BINS):
            bucket = [r for r, bi in zip(domain_pool, bin_idx) if bi == b]
            bucket.sort(key=lambda r: r["mean_aoa"])
            identity_selected.extend(bucket[: round(target_n * bin_frac[b])])
    print(f"identity pairs selected: {len(identity_selected)} (target {N_IDENTITY})")

    return build_identity_pairs(pl.DataFrame(identity_selected), "identity").with_columns(_diagnostic_null_columns())


def load_scripture_pairs(barec: pl.DataFrame) -> pl.DataFrame:
    is_scripture = pl.col("Source").is_in(SCRIPTURE_SOURCES)
    scripture_pool = barec.filter(is_scripture)
    scripture_sample = scripture_pool.sample(n=min(N_SCRIPTURE, scripture_pool.shape[0]), seed=42, shuffle=True)
    return build_identity_pairs(scripture_sample, "scripture").with_columns(_diagnostic_null_columns())


def main() -> None:
    generated_df = load_generated_pairs()
    barec = load_and_clean_barec()
    identity_df = load_identity_pairs(generated_df, barec)
    scripture_df = load_scripture_pairs(barec)
    print(f"scripture pairs selected: {scripture_df.shape[0]}")

    final = pl.concat([generated_df, identity_df, scripture_df])
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    final.write_parquet(OUT_PATH)

    print(f"\nFINAL provisional dataset: {final.shape[0]} rows")
    print(final["pair_type"].value_counts())


if __name__ == "__main__":
    main()
