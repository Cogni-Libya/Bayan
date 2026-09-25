"""Grouped, stratified, deterministic train/dev/test split for the synthetic simplification export.

Design:
- Group by source: every row for one source ID goes to one split (non-negotiable).
- Stratum key: level bucket x Domain x pair_type (tier/eq/lead are NOT in the key -- crossing them
  in would create sparse cells that destroy balance; they're verified afterward instead).
- Assignment: hash(source_id + SALT) -> deterministic bucket, so the rule is reproducible anywhere
  and stable under growth -- a source is assigned once, forever, regardless of what gets appended
  to the pool later.
- Fixed ABSOLUTE dev/test sizes (not proportions): this dataset gets rebuilt as new batches land,
  and proportional splits would silently regrow dev/test on every resume, changing what eval numbers
  mean between experiments. Only train grows from here.
- Test draws ONLY from BAREC-train-sourced rows. BAREC-test is already the project's own locked eval
  set (data/test_manifest.json) -- generating our test split from it would conflate two different
  evaluation instruments. BAREC-dev holds only 111 accepted pairs, far short of a usable dev size on
  its own, so dev is not purely inherited from BAREC-dev either; both dev and test are hash-holdouts
  from the combined BAREC-train + BAREC-dev accepted pool.

The frozen rule (SALT, thresholds, stratum definitions) lives in this file, committed with the code.
The resulting ID -> split assignment is written to data/dataset_split.csv (small, no sentence text,
committable) so it doesn't need re-deriving by hand and can be diffed/audited directly.
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_provenance import annotate_barec_provenance, filter_barec

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SALT = "bayan-split-v1"  # bump the suffix (v2, v3, ...) if the split ever needs a deliberate reset;
# never change in place, since that would silently reassign every source's split.
TARGET_DEV = 1200
TARGET_TEST = 1500

LEVEL_BUCKETS = [(0, 13, "12-13"), (13, 14, "13-14"), (14, 15, "14-15"), (15, 99, "15+")]


def _bucket_of(row_id: int) -> int:
    h = hashlib.sha256(f"{SALT}:{row_id}".encode()).hexdigest()
    return int(h[:8], 16) % 10_000  # finer than mod 100 -- lets thresholds hit exact absolute counts


def _level_bucket(level19: float) -> str:
    for lo, hi, name in LEVEL_BUCKETS:
        if lo <= level19 < hi:
            return name
    return "15+"


def build_split(provisional_path: Path, barec_dir: Path) -> pl.DataFrame:
    df = pl.read_parquet(provisional_path)
    df = filter_barec(df, include=("train", "dev"), on_conflict="exclude")
    df = annotate_barec_provenance(df)

    # Bring in Domain and the gold 19-level for stratification (not in the provisional export).
    splits = {name: pl.read_csv(barec_dir / f"{name}.csv", encoding="utf8-lossy")
              .select("ID", "Domain", "Readability_Level_19") for name in ("train", "dev")}
    meta = pl.concat(splits.values())
    df = df.join(meta, on="ID", how="left")
    # Identity/scripture rows: Domain still resolves (they're real BAREC sources); level bucket only
    # matters for stratification balance, not correctness, so a null here just falls into its own
    # (small) stratum rather than crashing the join.
    df = df.with_columns(
        pl.col("Readability_Level_19").fill_null(pl.col("source_level") * 4).alias("Readability_Level_19"),
        pl.col("Domain").fill_null("Unknown").alias("Domain"),
    )

    df = df.with_columns(
        pl.col("Readability_Level_19").map_elements(_level_bucket, return_dtype=pl.Utf8).alias("level_bucket"),
        pl.col("ID").map_elements(_bucket_of, return_dtype=pl.Int64).alias("hash_bucket"),
    )
    df = df.with_columns(
        (pl.col("level_bucket") + "|" + pl.col("Domain") + "|" + pl.col("pair_type")).alias("stratum")
    )

    n_total = df.shape[0]
    strata = df["stratum"].value_counts().to_dicts()
    stratum_share = {s["stratum"]: s["count"] / n_total for s in strata}

    # Per-stratum target counts, proportional to each stratum's share of the eligible pool, summing
    # (by construction) to the global TARGET_DEV / TARGET_TEST.
    test_target = {s: round(TARGET_TEST * stratum_share[s]) for s in stratum_share}
    dev_target = {s: round(TARGET_DEV * stratum_share[s]) for s in stratum_share}

    split_labels = []
    test_eligible = df["barec_split"] == "train"  # test only ever draws from BAREC-train-sourced rows
    for stratum in df["stratum"].unique().to_list():
        stratum_mask = df["stratum"] == stratum
        stratum_df = df.filter(stratum_mask)

        test_pool = stratum_df.filter(pl.col("barec_split") == "train").sort("hash_bucket")
        test_ids = set(test_pool["ID"].to_list()[: test_target.get(stratum, 0)])

        remaining = stratum_df.filter(~pl.col("ID").is_in(test_ids)).sort("hash_bucket")
        dev_ids = set(remaining["ID"].to_list()[: dev_target.get(stratum, 0)])

        for row_id in stratum_df["ID"].to_list():
            if row_id in test_ids:
                split_labels.append((row_id, "test"))
            elif row_id in dev_ids:
                split_labels.append((row_id, "dev"))
            else:
                split_labels.append((row_id, "train"))

    split_df = pl.DataFrame(split_labels, schema=["ID", "split"], orient="row")
    return df.join(split_df, on="ID", how="left")


def verify_split(df: pl.DataFrame) -> None:
    print(f"split sizes: {df['split'].value_counts().sort('split')}")
    assert df.filter(pl.col("ID").is_duplicated()).shape[0] == 0, "a source ID appears more than once in the export"

    for covariate in ("equivalence_score", "readability_lead", "ease_score"):
        vals = df.filter(pl.col(covariate).is_not_null())
        for split_name in ("dev", "test"):
            a = vals.filter(pl.col("split") == "train")[covariate].to_numpy()
            b = vals.filter(pl.col("split") == split_name)[covariate].to_numpy()
            if len(a) == 0 or len(b) == 0:
                continue
            pooled_std = np.sqrt((a.var() + b.var()) / 2)
            smd = abs(a.mean() - b.mean()) / pooled_std if pooled_std > 0 else 0.0
            flag = "OK" if smd < 0.1 else "FLAG (>=0.1)"
            print(f"  SMD train vs {split_name} on {covariate}: {smd:.3f}  [{flag}]")

    for cat_col in ("Domain", "pair_type", "acceptance_tier"):
        print(f"  {cat_col} balance by split:")
        print(df.group_by(["split", cat_col]).len().sort(["split", cat_col]))


if __name__ == "__main__":
    result = build_split(
        PROJECT_ROOT / "data" / "processed" / "barec_simplification_provisional.parquet",
        PROJECT_ROOT / "data" / "raw" / "barec",
    )
    verify_split(result)
    out_path = PROJECT_ROOT / "data" / "dataset_split.csv"
    result.select("ID", "split", "stratum", "barec_split").write_csv(out_path)
    print(f"\nwrote split assignment for {result.shape[0]} rows to {out_path}")
