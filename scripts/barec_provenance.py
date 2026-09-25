"""BAREC split provenance: which train/dev/test split a text or source ID actually came from.

A provenance-*labeling* function, not a boolean filter and not a split-owner -- callers express
policy in one line (`annotate_barec_provenance(df).filter(pl.col("barec_split") != "test")`); this
module's only job is ground truth about where a text came from. A filter baked silently into the
loader would hide from callers which rows were dropped and why; an explicit label is auditable and
overridable instead.

Matching: exact source ID first (this project's own pipeline always logs the BAREC `ID` -- see
`barec_simplification_pipeline.py`'s KEEP_COLS -- so ID matching is exact, not a heuristic, for our
own data). Falls back to normalized-text matching (reusing check_leakage.py's own `normalize()` for
one shared definition of "the same sentence" across the project's tools) for text without a known
ID. Diacritic stripping in that normalizer is a real collision risk for provenance specifically
(two genuinely different short sentences can collapse to the same skeleton) -- text-fallback matches
are flagged `match_method="text"` (vs `"id"`) precisely so a data card or downstream consumer can
weight that distinction, not silently treat both the same.

Cross-split duplicates: BAREC repeats 311 sentences between its own train and test splits (see
scripts/evaluation/README.md). A row whose own ID is in train can still have IDENTICAL TEXT to some
test-split row under a different ID -- ID-only matching misses this. `is_duplicate_across_splits`
flags it; the conservative rule (a match to test *anywhere* disqualifies) is left to callers via
`filter_barec`, not hardcoded here, since this module only reports.
"""
from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent / "evaluation"))
from check_leakage import normalize  # one shared definition of "the same sentence" project-wide

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BAREC_DIR = PROJECT_ROOT / "data" / "raw" / "barec"
SPLIT_NAMES = ("train", "dev", "test")


def _barec_file_hash() -> str:
    """Hash of the three raw BAREC files, for version-pinning exports and the data card --
    if BAREC is ever refetched/updated, exports made against a different hash are distinguishable."""
    h = hashlib.sha256()
    for name in SPLIT_NAMES:
        h.update((BAREC_DIR / f"{name}.csv").read_bytes())
    return h.hexdigest()[:16]


def _load_barec_splits() -> dict[str, pl.DataFrame]:
    return {
        name: pl.read_csv(BAREC_DIR / f"{name}.csv", encoding="utf8-lossy").select("ID", "Sentence")
        for name in SPLIT_NAMES
    }


def annotate_barec_provenance(
    items: pl.DataFrame, id_col: str = "ID", text_col: str = "original_text"
) -> pl.DataFrame:
    """items needs at least one of id_col / text_col. Returns items with three columns added:
    barec_split ("train"/"dev"/"test"/"unknown"), match_method ("id"/"text"/"none"),
    is_duplicate_across_splits (bool -- text also found in a split other than barec_split, by exact
    normalized-text match, no length floor). This exact-match count reproduces the team's own
    documented "BAREC repeats 311 sentences between train and test" (scripts/evaluation/README.md)
    precisely -- that figure is a raw corpus characterization, computed without check_leakage.py's
    --min-words (which exists to stop *short generated text* from spuriously matching everything
    during leakage comparison, a different concern from counting BAREC's own exact repeats). Some
    of these 311 are trivial (a bare name, a one-word title) -- real but low-stakes; report them,
    don't silently drop them from the count, and let filter_barec's caller decide what to do with a
    short one via on_conflict."""
    splits = _load_barec_splits()

    id_to_split: dict[int, str] = {}
    id_to_text: dict[int, str] = {}
    text_to_splits: dict[str, set[str]] = {}
    for name, df in splits.items():
        for row_id, text in zip(df["ID"].to_list(), df["Sentence"].to_list()):
            id_to_split.setdefault(row_id, name)  # first split wins if an ID somehow repeats
            id_to_text.setdefault(row_id, text)
            text_to_splits.setdefault(normalize(text), set()).add(name)

    has_id = id_col in items.columns
    has_text = text_col in items.columns
    if not has_id and not has_text:
        raise ValueError(f"items needs an '{id_col}' or '{text_col}' column")

    barec_split, match_method, is_dup = [], [], []
    for row in items.iter_rows(named=True):
        split = None
        method = "none"
        # Prefer the matched split's own canonical text (from ID lookup) over the input's own
        # text_col for the duplicate check -- id_to_text is guaranteed clean BAREC text, whereas
        # a generated pair's original_text should match it but isn't the authority.
        text_for_dup_check = None
        if has_id and row[id_col] in id_to_split:
            split = id_to_split[row[id_col]]
            method = "id"
            text_for_dup_check = id_to_text[row[id_col]]
        elif has_text:
            norm = normalize(row[text_col])
            hit_splits = text_to_splits.get(norm)
            if hit_splits:
                split = sorted(hit_splits)[0]  # deterministic; cross-split dup flag carries the rest
                method = "text"
                text_for_dup_check = row[text_col]
        if text_for_dup_check is None and has_text:
            text_for_dup_check = row[text_col]

        barec_split.append(split or "unknown")
        match_method.append(method)
        if text_for_dup_check is not None:
            hit_splits = text_to_splits.get(normalize(text_for_dup_check), set())
            is_dup.append(len(hit_splits) > 1)
        else:
            is_dup.append(False)

    return items.with_columns(
        pl.Series("barec_split", barec_split),
        pl.Series("match_method", match_method),
        pl.Series("is_duplicate_across_splits", is_dup),
    )


def filter_barec(
    items: pl.DataFrame, include: tuple[str, ...] = ("train", "dev"), on_conflict: str = "exclude"
) -> pl.DataFrame:
    """Thin policy shim over annotate_barec_provenance. on_conflict="exclude" drops any row whose
    text is also findable in a split outside `include` (the conservative "a match to test anywhere
    disqualifies" rule) -- pass "ignore" to only filter by barec_split itself."""
    annotated = annotate_barec_provenance(items) if "barec_split" not in items.columns else items
    kept = annotated.filter(pl.col("barec_split").is_in(include))
    if on_conflict == "exclude" and "test" not in include and kept.shape[0]:
        # is_duplicate_across_splits alone doesn't say WHICH other split -- re-check specifically
        # against "test", since that's the one disqualifying split regardless of `include` (a
        # train/dev cross-duplicate is fine; a train/test or dev/test one is not).
        splits = _load_barec_splits()
        test_norms = {normalize(t) for t in splits["test"]["Sentence"].to_list()}
        id_to_text = {i: t for name in ("train", "dev") for i, t in
                      zip(splits[name]["ID"].to_list(), splits[name]["Sentence"].to_list())}

        def _leaks_to_test(row: dict) -> bool:
            text = row.get("original_text") or id_to_text.get(row.get("ID"))
            return text is not None and normalize(text) in test_norms

        leak_mask = pl.Series([_leaks_to_test(r) for r in kept.iter_rows(named=True)])
        kept = kept.filter(~leak_mask)
    return kept


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", required=True, help="jsonl or parquet file with an ID and/or original_text column")
    parser.add_argument("--out", required=True, help="annotated output path (same format as input)")
    parser.add_argument("--report", action="store_true", help="print split/unknown/collision counts")
    args = parser.parse_args()

    path = Path(args.data)
    df = pl.read_ndjson(path) if path.suffix == ".jsonl" else pl.read_parquet(path)
    annotated = annotate_barec_provenance(df)

    out_path = Path(args.out)
    if out_path.suffix == ".jsonl":
        annotated.write_ndjson(out_path)
    else:
        annotated.write_parquet(out_path)

    if args.report:
        print(f"BAREC file hash: {_barec_file_hash()}")
        print(annotated["barec_split"].value_counts().sort("barec_split"))
        print(annotated["match_method"].value_counts().sort("match_method"))
        n_dup = annotated["is_duplicate_across_splits"].sum()
        print(f"cross-split duplicates: {n_dup}")


if __name__ == "__main__":
    main()
