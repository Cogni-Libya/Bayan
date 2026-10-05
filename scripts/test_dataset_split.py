"""Regression tests for dataset_split.py's two hardest-to-eyeball invariants -- both were real bugs
found only by hand in review (see the module's own docstring), so they're pinned here instead of
staying manually-verified-once claims in the data card. Run with:
uv run python scripts/test_dataset_split.py

Uses real BAREC train IDs (annotate_barec_provenance matches by ID first, ignoring the fabricated
`original_text` below -- see barec_provenance.py) so build_split's real provenance/meta joins work
without a synthetic BAREC fixture. All thresholds-file I/O is redirected to a temp path so these
tests never touch the real data/dataset_split_thresholds.json.
"""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import polars as pl

import dataset_split as ds

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REAL_BAREC_DIR = PROJECT_ROOT / "data" / "raw" / "barec"

_train = pl.read_csv(REAL_BAREC_DIR / "train.csv", encoding="utf8-lossy").sort("ID")
REAL_TRAIN_IDS = _train["ID"].to_list()  # stable, ID-ascending; just needs to be real+in-train


def _row(row_id: int, original_text: str, pair_type: str = "generated") -> dict:
    return {
        "ID": row_id, "original_text": original_text, "simplified_text": "نص مبسط للاختبار",
        "source_level": 3, "predicted_level": 1, "equivalent": True, "equivalence_reasoning": "test",
        "is_easy": True, "pair_type": pair_type, "equivalence_score": 0.9, "acceptance_tier": "A",
        "readability_lead": 1.0, "ease_score": 0.0, "d_logit": 1.0, "provisional": True,
    }


def _run_build(rows: list[dict], thresholds_path: Path) -> pl.DataFrame:
    with tempfile.TemporaryDirectory() as td:
        provisional_path = Path(td) / "provisional.parquet"
        pl.DataFrame(rows).write_parquet(provisional_path)
        old_path = ds.THRESHOLDS_PATH
        ds.THRESHOLDS_PATH = thresholds_path
        try:
            return ds.build_split(provisional_path, REAL_BAREC_DIR)
        finally:
            ds.THRESHOLDS_PATH = old_path


def test_pool_growth_does_not_move_existing_rows():
    base_ids = REAL_TRAIN_IDS[:40]
    base_rows = [_row(i, f"نص أساسي رقم {i}", pair_type="generated" if i % 2 else "identity")
                 for i in base_ids]
    with tempfile.TemporaryDirectory() as td:
        thresholds_path = Path(td) / "thresholds.json"
        first = _run_build(base_rows, thresholds_path)
        first_splits = dict(zip(first["ID"].to_list(), first["split"].to_list()))

        grown_ids = REAL_TRAIN_IDS[40:60]
        grown_rows = base_rows + [_row(i, f"نص جديد رقم {i}", pair_type="generated" if i % 2 else "identity")
                                   for i in grown_ids]
        second = _run_build(grown_rows, thresholds_path)
        second_splits = dict(zip(second["ID"].to_list(), second["split"].to_list()))

    moved = [i for i in base_ids if first_splits[i] != second_splits[i]]
    assert not moved, f"{len(moved)} existing rows changed split after the pool grew: {moved}"


def test_cross_stratum_group_uses_canonical_rows_stratum():
    """Two rows sharing one normalized text but sitting in different strata (here: different
    barec_split, the sharpest case -- one 'train', one an impossible/unknown value that would be
    obviously wrong if picked). The bug this guards against (_group_by_canonical_text, formerly
    inline in build_split) picked whichever row polars saw first for the group's stratum/
    barec_split, independent of ID -- so the group's outcome depended on input row order, not on
    which row is actually canonical (min-ID). Testing at this level (not through build_split) avoids
    a confound: with only one text-group in a tiny synthetic pool, every stratum gets the same
    threshold regardless of which one is picked (share = 1/1 either way), so a full-pipeline
    equality check on `split` can pass even when the underlying stratum-selection bug is present."""
    id_lo, id_hi = 10, 20  # id_lo is canonical (min); a real ID isn't needed at this level
    row_lo = {"ID": id_lo, "norm_text": "شارك", "stratum": "STRATUM-FROM-LOW-ID", "barec_split": "train"}
    row_hi = {"ID": id_hi, "norm_text": "شارك", "stratum": "STRATUM-FROM-HIGH-ID", "barec_split": "dev"}

    groups_lo_first = ds._group_by_canonical_text(pl.DataFrame([row_lo, row_hi]))
    groups_hi_first = ds._group_by_canonical_text(pl.DataFrame([row_hi, row_lo]))

    for name, groups in (("[lo, hi] order", groups_lo_first), ("[hi, lo] order", groups_hi_first)):
        assert groups.shape[0] == 1, f"{name}: expected the two rows to merge into one group"
        got_stratum = groups["stratum"][0]
        got_barec_split = groups["barec_split"][0]
        assert got_stratum == "STRATUM-FROM-LOW-ID", (
            f"{name}: group's stratum was {got_stratum!r}, expected the canonical (min-ID) row's "
            "stratum regardless of input order"
        )
        assert got_barec_split == "train", (
            f"{name}: group's barec_split was {got_barec_split!r}, expected the canonical row's 'train'"
        )


def test_normalize_version_mismatch_raises():
    with tempfile.TemporaryDirectory() as td:
        thresholds_path = Path(td) / "thresholds.json"
        thresholds_path.write_text(json.dumps({
            "_normalize_version": "0000000000000000",
            "12-13|Unknown|generated": {"test_threshold": 100, "dev_width": 50},
        }))
        old_path = ds.THRESHOLDS_PATH
        ds.THRESHOLDS_PATH = thresholds_path
        try:
            try:
                ds._load_thresholds()
                raised = False
            except SystemExit:
                raised = True
        finally:
            ds.THRESHOLDS_PATH = old_path
    assert raised, "a pinned normalize_version mismatch must raise, not silently continue"


def test_normalize_version_migrates_old_format_file():
    with tempfile.TemporaryDirectory() as td:
        thresholds_path = Path(td) / "thresholds.json"
        thresholds_path.write_text(json.dumps({
            "12-13|Unknown|generated": {"test_threshold": 100, "dev_width": 50},
        }))  # old format: no _normalize_version key at all
        old_path = ds.THRESHOLDS_PATH
        ds.THRESHOLDS_PATH = thresholds_path
        try:
            data = ds._load_thresholds()
        finally:
            ds.THRESHOLDS_PATH = old_path
    assert data["_normalize_version"] == ds._NORMALIZE_VERSION


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  OK  {t.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {t.__name__}: {e}")
    print(f"\n{len(tests) - failed}/{len(tests)} passed")
    sys.exit(1 if failed else 0)
