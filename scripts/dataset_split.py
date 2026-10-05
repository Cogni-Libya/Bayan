"""Grouped, stratified, deterministic train/dev/test split for the synthetic simplification export.

Design:
- Group by normalized TEXT, not just source ID: BAREC repeats sentences under different IDs, so
  grouping by ID alone lets the same underlying sentence land in two different splits (a real bug
  found in review -- fixed here by assigning one split per unique normalized text, then propagating
  it to every ID that shares that text).
- Stratum key: level bucket x Domain x pair_type (tier/eq/lead are NOT in the key -- crossing them
  in would create sparse cells that destroy balance; they're verified afterward instead).
- Assignment: a FROZEN per-stratum hash-bucket THRESHOLD, not a recomputed target count. The
  earlier version computed `target_count = round(TARGET * current_stratum_share)` fresh on every
  run and took the "first N by hash" -- since stratum_share depends on the current pool size, N
  moves every time the pool grows, and a source that was in test today can slide into train
  tomorrow even though its own hash never changed. Fixed by converting the target into a bucket
  THRESHOLD once, persisting it to data/dataset_split_thresholds.json, and reusing that exact
  threshold on every future run for strata that already have one -- a source's fate then depends
  only on (its own fixed hash, a threshold that never changes for its stratum), which is what
  "frozen" actually requires. Only brand-new strata (one that's never been seen before) get a
  fresh threshold computed and then frozen in turn.
- The thresholds freeze each row's split, not the split sizes: a row already assigned never moves,
  but new batches add to dev and test as well as train. Because a new stratum's threshold is
  TARGET * share / count = TARGET / n_groups, every stratum seen so far has the same thresholds, so
  in practice this is one global cut (about 11.7% test, 9.3% dev at the first freeze).
- Test draws ONLY from BAREC-train-sourced rows. BAREC-test is already the project's own locked eval
  set (data/test_manifest.json) -- generating our test split from it would conflate two different
  evaluation instruments. BAREC-dev holds only 111 accepted pairs, far short of a usable dev size on
  its own, so dev is not purely inherited from BAREC-dev either; both dev and test are hash-holdouts
  from the combined BAREC-train + BAREC-dev accepted pool.

The frozen thresholds live in data/dataset_split_thresholds.json, committed with the code, alongside
this file's SALT. The resulting ID -> split assignment is written to data/dataset_split.csv (small,
no sentence text, committable) so it doesn't need re-deriving by hand and can be diffed/audited.
"""
from __future__ import annotations

import hashlib
import inspect
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_provenance import annotate_barec_provenance, filter_barec
from check_leakage import normalize as normalize_text  # one shared "same sentence" definition

# The group KEY is normalize_text(original_text) -- if normalize() ever changes (e.g. a future
# punctuation/dash fix like the one already made once), the group key changes too, and existing
# rows can silently cross the frozen threshold without anyone touching SALT or the thresholds file.
# Pinning a hash of its actual source (not a hand-maintained version string, which is easy to forget
# to bump) makes that drift loud instead of silent.
_NORMALIZE_VERSION = hashlib.sha256(inspect.getsource(normalize_text).encode()).hexdigest()[:16]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SALT = "bayan-split-v1"  # bump the suffix (v2, v3, ...) for a deliberate reset; never change in
# place, since that would silently reassign every source's split.
TARGET_DEV = 1200
TARGET_TEST = 1500
THRESHOLDS_PATH = PROJECT_ROOT / "data" / "dataset_split_thresholds.json"
HASH_SPACE = 10_000  # bucket resolution -- fine enough that rounding a target proportion to an
# integer bucket threshold doesn't visibly distort small strata.

LEVEL_BUCKETS = [(0, 13, "12-13"), (13, 14, "13-14"), (14, 15, "14-15"), (15, 99, "15+")]


def _bucket_of(key: str) -> int:
    h = hashlib.sha256(f"{SALT}:{key}".encode()).hexdigest()
    return int(h[:8], 16) % HASH_SPACE


def _level_bucket(level19: float) -> str:
    for lo, hi, name in LEVEL_BUCKETS:
        if lo <= level19 < hi:
            return name
    return "15+"


def _load_thresholds() -> dict:
    if not THRESHOLDS_PATH.exists():
        return {"_normalize_version": _NORMALIZE_VERSION}
    data = json.loads(THRESHOLDS_PATH.read_text())
    pinned = data.get("_normalize_version")
    if pinned is not None and pinned != _NORMALIZE_VERSION:
        raise SystemExit(
            f"normalize() has changed since {THRESHOLDS_PATH} was frozen (pinned {pinned}, now "
            f"{_NORMALIZE_VERSION}) -- every existing group's split membership may silently shift "
            "under the new grouping key. This needs a deliberate decision (bump SALT for a full "
            "reset, or a migration that re-derives thresholds while preserving existing rows' "
            "splits), not a silent continue."
        )
    data.setdefault("_normalize_version", _NORMALIZE_VERSION)
    return data


def _group_by_canonical_text(df: pl.DataFrame) -> pl.DataFrame:
    """One row per unique normalized text: canonical_id = min(ID) sharing that text, its own
    barec_split governs test-eligibility for the whole group (sorted by ID first, so .first() is
    the canonical row's value on every run, not whichever row polars happens to see first), and its
    hash decides the whole group's split -- every ID sharing that text inherits the same split,
    closing the bug where the same sentence under different IDs could land on both sides of the
    split. Split out from build_split so this specific invariant (not the threshold math around it)
    is directly testable -- see test_dataset_split.py."""
    return (
        df.sort("ID")
        .group_by("norm_text", maintain_order=True)
        .agg(
            pl.col("ID").min().alias("canonical_id"),
            pl.col("ID").alias("member_ids"),
            pl.col("stratum").first(),
            pl.col("barec_split").first(),
        )
        .with_columns(pl.col("canonical_id").cast(pl.Utf8).map_elements(_bucket_of, return_dtype=pl.Int64).alias("hash_bucket"))
    )


def build_split(provisional_path: Path, barec_dir: Path) -> pl.DataFrame:
    df = pl.read_parquet(provisional_path)
    df = filter_barec(df, include=("train", "dev"), on_conflict="exclude")
    df = annotate_barec_provenance(df)

    splits = {name: pl.read_csv(barec_dir / f"{name}.csv", encoding="utf8-lossy")
              .select("ID", "Domain", "Readability_Level_19") for name in ("train", "dev")}
    meta = pl.concat(splits.values())
    df = df.join(meta, on="ID", how="left")
    df = df.with_columns(
        pl.col("Readability_Level_19").fill_null(pl.col("source_level") * 4).alias("Readability_Level_19"),
        pl.col("Domain").fill_null("Unknown").alias("Domain"),
    )
    df = df.with_columns(
        pl.col("Readability_Level_19").map_elements(_level_bucket, return_dtype=pl.Utf8).alias("level_bucket"),
        pl.col("original_text").map_elements(normalize_text, return_dtype=pl.Utf8).alias("norm_text"),
    )
    df = df.with_columns(
        (pl.col("level_bucket") + "|" + pl.col("Domain") + "|" + pl.col("pair_type")).alias("stratum")
    )

    groups = _group_by_canonical_text(df)

    thresholds = _load_thresholds()
    n_groups = groups.shape[0]
    stratum_counts = groups["stratum"].value_counts().to_dicts()
    stratum_share = {s["stratum"]: s["count"] / n_groups for s in stratum_counts}

    for stratum in stratum_share:
        if stratum not in thresholds:
            # Brand-new stratum: compute a fresh threshold now, from the current pool, and freeze it.
            test_frac = TARGET_TEST * stratum_share[stratum] / max(stratum_counts_by_name(stratum_counts, stratum), 1)
            dev_frac = TARGET_DEV * stratum_share[stratum] / max(stratum_counts_by_name(stratum_counts, stratum), 1)
            thresholds[stratum] = {
                "test_threshold": min(round(test_frac * HASH_SPACE), HASH_SPACE),
                "dev_width": min(round(dev_frac * HASH_SPACE), HASH_SPACE),
            }
    # Always write, not just when a new stratum was added: `_load_thresholds()` migrates an
    # old-format file (adding `_normalize_version`) in memory, and that migration needs to actually
    # land on disk even when no stratum-level change happened this run -- a real bug in an earlier
    # version, found by checking the file's own content after a run rather than trusting `updated`.
    THRESHOLDS_PATH.write_text(json.dumps(thresholds, indent=2, ensure_ascii=False, sort_keys=True))

    def _assign(row: dict) -> str:
        th = thresholds[row["stratum"]]
        if row["barec_split"] == "train" and row["hash_bucket"] < th["test_threshold"]:
            return "test"
        if row["hash_bucket"] < th["test_threshold"] + th["dev_width"]:
            return "dev"
        return "train"

    groups = groups.with_columns(
        pl.struct(["stratum", "barec_split", "hash_bucket"]).map_elements(_assign, return_dtype=pl.Utf8).alias("split")
    )

    id_to_split = {}
    for row in groups.iter_rows(named=True):
        for member_id in row["member_ids"]:
            id_to_split[member_id] = row["split"]

    split_df = pl.DataFrame({"ID": list(id_to_split.keys()), "split": list(id_to_split.values())})
    return df.join(split_df, on="ID", how="left")


def stratum_counts_by_name(stratum_counts: list[dict], stratum: str) -> int:
    for s in stratum_counts:
        if s["stratum"] == stratum:
            return s["count"]
    return 1


def verify_split(df: pl.DataFrame) -> None:
    print(f"split sizes: {df['split'].value_counts().sort('split')}")
    assert df.filter(pl.col("ID").is_duplicated()).shape[0] == 0, "a source ID appears more than once in the export"

    cross = df.group_by("norm_text").agg(pl.col("split").n_unique().alias("n")).filter(pl.col("n") > 1)
    assert cross.shape[0] == 0, f"{cross.shape[0]} source texts appear in more than one split"

    for covariate in ("equivalence_score", "readability_lead", "ease_score"):
        if covariate not in df.columns:
            continue
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
