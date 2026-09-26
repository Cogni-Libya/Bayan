"""Pinned-fixture tests for barec_provenance.py -- known-train/test/unknown IDs and the one
cross-split duplicate this module exists to catch. Run with: uv run python scripts/test_barec_provenance.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import polars as pl
from barec_provenance import annotate_barec_provenance, filter_barec

# Pinned fixtures -- re-derive if BAREC is ever refetched (check _barec_file_hash() first).
KNOWN_TRAIN_ID = 10100290015        # data/raw/barec/train.csv -- long, verified not in test_norms
KNOWN_TEST_ID = 10102220001         # data/raw/barec/test.csv, row 1
KNOWN_UNKNOWN_ID = 999999999999999  # not a real BAREC ID
KNOWN_TRAIN_TEST_DUP_ID = 10102570041  # train ID whose text ALSO appears in test (one of the 311)


def test_known_train():
    r = annotate_barec_provenance(pl.DataFrame({"ID": [KNOWN_TRAIN_ID]}))
    assert r["barec_split"][0] == "train", r
    assert r["match_method"][0] == "id"


def test_known_test():
    r = annotate_barec_provenance(pl.DataFrame({"ID": [KNOWN_TEST_ID]}))
    assert r["barec_split"][0] == "test", r


def test_unknown():
    r = annotate_barec_provenance(pl.DataFrame({"ID": [KNOWN_UNKNOWN_ID]}))
    assert r["barec_split"][0] == "unknown", r
    assert r["match_method"][0] == "none"


def test_cross_split_duplicate_detected():
    r = annotate_barec_provenance(pl.DataFrame({"ID": [KNOWN_TRAIN_TEST_DUP_ID]}))
    assert r["barec_split"][0] == "train"  # its own ID's split
    assert r["is_duplicate_across_splits"][0] is True


def test_filter_barec_excludes_train_test_duplicate():
    sample = pl.DataFrame({"ID": [KNOWN_TRAIN_ID, KNOWN_TRAIN_TEST_DUP_ID, KNOWN_TEST_ID]})
    kept = filter_barec(sample, include=("train", "dev"))
    kept_ids = set(kept["ID"].to_list())
    assert KNOWN_TRAIN_ID in kept_ids, "a clean train row must survive the filter"
    assert KNOWN_TRAIN_TEST_DUP_ID not in kept_ids, "a train row whose text leaks into test must be excluded"
    assert KNOWN_TEST_ID not in kept_ids, "test-split rows must never survive a train/dev filter"


def test_315_train_test_duplicates_pinned():
    """is_duplicate_across_splits flags ANY other split (train/dev overlap counts too, and that's
    correct for the general-purpose flag -- filter_barec re-checks test specifically for exclusion).
    This test validates against the team's documented train-vs-test figure directly, by unique
    normalized text (not row count -- BAREC repeats generic headings like "الفصل الأول" dozens of
    times within a single split, which inflates a row-count comparison). 311 in the original
    scripts/evaluation/README.md count; 315 once normalize() also strips em/en-dash (a real gap
    found in review -- those dashes appear in real BAREC sentences and were silently surviving
    normalization, letting 4 more genuine duplicates through undetected)."""
    from check_leakage import normalize as _normalize

    train = pl.read_csv("data/raw/barec/train.csv", encoding="utf8-lossy")
    test = pl.read_csv("data/raw/barec/test.csv", encoding="utf8-lossy")
    train_norms = {_normalize(s) for s in train["Sentence"].to_list()}
    test_norms = {_normalize(s) for s in test["Sentence"].to_list()}
    n_dup = len(train_norms & test_norms)
    assert n_dup == 315, f"expected 315 train/test duplicates (post dash-fix), got {n_dup}"


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
