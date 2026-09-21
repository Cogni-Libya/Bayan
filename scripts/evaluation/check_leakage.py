"""
Leakage check for Bayan.

Usage:
    uv run python scripts/evaluation/check_leakage.py <training_file>              # against every locked test set
    uv run python scripts/evaluation/check_leakage.py <training_file> <test_file>  # against one

Compares a training file's sentences against the locked test sentences, looking for
exact matches and near-duplicates. Exits with an error if anything is found.

Reads .jsonl, .csv, .tsv and .parquet, and compares every column that holds sentences. For the
SAMER test set that means L5, L4 and L3 together: a simplified target that turns up in
training is leakage just as much as a source sentence is.
"""
import argparse
import csv
import json
import re
import string
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # scripts/evaluation/ -> repo root
LOCKED_DIR = REPO_ROOT / "data" / "test_locked"

# Ordered groups: the first group with any column present wins, and every present
# column in it is read. Groups rather than one flat list because "source" means a
# sentence in a training file but a corpus name ("Hindawi", "Wikipedia") in our
# generated pairs — a flat list would compare those as if they were sentences.
TEXT_COLUMN_GROUPS = (
    ("original_text", "simplified_text"),  # our generated pairs
    ("L5", "L4", "L3"),                    # SAMER — all three levels are test material
    ("Sentence",),                         # BAREC
    ("text",),                             # queue files, which also carry a "source" label
    ("source", "target", "prediction"),    # plain training / scoring shorthand
)

# Diacritics — same set as score.py
_ARABIC_DIACRITICS = re.compile(
    r"[ؐ-ًؚ-ٟۖ-ۜ۟-۪ۨ-ۭࣔ-ࣣ࣡-ࣿ]"
)

# Arabic punctuation not covered by string.punctuation
_ARABIC_PUNCTUATION = "،؛؟«»ـ"

_ALEF_VARIANTS = re.compile(r"[أإآ]")


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize(text: str) -> str:
    """Normalize Arabic text for leakage comparison:
    strip diacritics, strip punctuation, unify alef/ta-marbuta/ya forms."""
    text = _ARABIC_DIACRITICS.sub("", text)
    text = _ALEF_VARIANTS.sub("ا", text)
    text = text.replace("ة", "ه")
    text = text.replace("ى", "ي")
    for ch in string.punctuation + _ARABIC_PUNCTUATION:
        text = text.replace(ch, "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _read_rows(path: Path) -> list[dict]:
    """Read a .jsonl, .csv, .tsv or .parquet file into a list of dicts.
    utf-8-sig because BAREC's CSV ships with a byte-order mark."""
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        import pandas as pd  # heavy, and only this branch needs it

        return pd.read_parquet(path).to_dict("records")
    with open(path, encoding="utf-8-sig", newline="") as f:
        if suffix in (".jsonl", ".json"):
            rows = []
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise SystemExit(
                        f"{path}: line {line_num} is not valid JSON. "
                        f"Expected one JSON object per line."
                    ) from exc
            return rows
        if suffix in (".csv", ".tsv"):
            return list(csv.DictReader(f, delimiter="\t" if suffix == ".tsv" else ","))
    raise SystemExit(
        f"{path}: unsupported file type '{suffix}'. Expected .jsonl, .csv, .tsv or .parquet."
    )


def load_sentences(path: str | Path, columns: list[str] | None = None) -> list[str]:
    """Load every sentence from a file, taking all the text columns it has."""
    path = Path(path)
    rows = _read_rows(path)
    if not rows:
        return []

    if columns:
        present = [c for c in columns if c in rows[0]]
    else:
        present = next(
            ([c for c in group if c in rows[0]]
             for group in TEXT_COLUMN_GROUPS if any(c in rows[0] for c in group)),
            [],
        )
    if not present:
        raise SystemExit(
            f"{path}: no sentence column found. This file has: {sorted(rows[0])}. "
            f"Name the right one with --columns."
        )
    print(f"  {path.name}: reading {', '.join(present)}")

    sentences = []
    for row in rows:
        for column in present:
            value = (row.get(column) or "").strip()
            if value:
                sentences.append(value)
    return sentences


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def char_ngrams(text: str, n: int = 5) -> set[str]:
    """Character n-grams of normalized text, for overlap comparison."""
    if len(text) < n:
        return {text}
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def jaccard(ngrams_a: set[str], ngrams_b: set[str]) -> float:
    """Jaccard overlap between two n-gram sets."""
    if not ngrams_a or not ngrams_b:
        return 0.0
    return len(ngrams_a & ngrams_b) / len(ngrams_a | ngrams_b)


def ngram_overlap(a: str, b: str, n: int = 5) -> float:
    """Jaccard overlap between two strings' character n-gram sets."""
    return jaccard(char_ngrams(a, n), char_ngrams(b, n))


def is_substantive(train_sentence: str, test_sentence: str, min_words: int) -> bool:
    """Whether a match is long enough to be evidence of contamination.

    BAREC is sentence-level and full of one- and two-word rows ("ماجد", "نعم"), and
    it repeats 311 sentences between its own train and test splits. So short matches
    are a property of the corpus, not of anyone's training file, and failing on them
    means the check cries wolf on every BAREC-derived dataset and gets ignored.
    """
    return min(len(train_sentence.split()), len(test_sentence.split())) >= min_words


def check_leakage(
    training_sentences: list[str],
    test_sentences: list[str],
    overlap_threshold: float = 0.8,
) -> tuple[list[tuple[str, str]], list[tuple[str, str, float]]]:
    """
    Compare every training sentence against every test sentence.
    Returns (exact_matches, near_duplicates).
    exact_matches is a list of (train_sentence, test_sentence).
    near_duplicates is a list of (train_sentence, test_sentence, overlap_score).
    """
    test_normalized = [normalize(t) for t in test_sentences]
    test_ngrams = [char_ngrams(t) for t in test_normalized]
    test_exact = {}
    for normalized, original in zip(test_normalized, test_sentences):
        test_exact.setdefault(normalized, original)

    exact_matches = []
    near_duplicates = []

    for train_sentence in training_sentences:
        norm_train = normalize(train_sentence)

        if norm_train in test_exact:
            exact_matches.append((train_sentence, test_exact[norm_train]))
            continue  # an exact match is also a near-duplicate; don't double count

        train_ngrams = char_ngrams(norm_train)
        if not train_ngrams:
            continue

        # Jaccard >= t is impossible unless the two sets are within a factor of t in
        # size, so most pairs can be skipped on a length comparison alone.
        smallest = len(train_ngrams) * overlap_threshold
        largest = len(train_ngrams) / overlap_threshold

        for candidate_ngrams, original_test in zip(test_ngrams, test_sentences):
            if not smallest <= len(candidate_ngrams) <= largest:
                continue
            overlap = jaccard(train_ngrams, candidate_ngrams)
            if overlap >= overlap_threshold:
                near_duplicates.append((train_sentence, original_test, overlap))

    return exact_matches, near_duplicates


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def subtract_reachable(
    matches: list[tuple[str, str, float | None]],
    reachable: list[str],
    overlap_threshold: float,
) -> tuple[list[tuple[str, str, float | None]], int]:
    """Drop matches whose test sentence also exists in text the training file was
    allowed to use.

    BAREC repeats 311 sentences between its own train and test splits, and more
    again as near-duplicates. A generated pair built from a train row can therefore
    reproduce a test sentence without anyone ever touching the test split. Passing
    --reachable data/raw/barec/train.csv lets the check tell that apart from a
    training file that really did read the test data.

    Only the distinct test sentences that matched are re-checked, so this is cheap.
    """
    if not reachable:
        return matches, 0

    reachable_normalized = sorted({normalize(s) for s in reachable})
    reachable_exact = set(reachable_normalized)

    verdict: dict[str, bool] = {}
    for _, test_sentence, _ in matches:
        normalized = normalize(test_sentence)
        if normalized in verdict:
            continue
        if normalized in reachable_exact:
            verdict[normalized] = True
            continue
        exact, near = check_leakage([test_sentence], reachable_normalized, overlap_threshold)
        verdict[normalized] = bool(exact or near)

    kept = [m for m in matches if not verdict[normalize(m[1])]]
    return kept, len(matches) - len(kept)


def locked_test_files() -> list[Path]:
    """Every file in data/test_locked/, which is git-ignored — see data/test_manifest.json."""
    if not LOCKED_DIR.is_dir():
        raise SystemExit(
            f"{LOCKED_DIR} does not exist. The locked test files are never committed — "
            f"copy them in and check them against data/test_manifest.json, or pass a test "
            f"file directly as the second argument."
        )
    files = sorted(p for p in LOCKED_DIR.iterdir() if p.is_file())
    if not files:
        raise SystemExit(f"{LOCKED_DIR} is empty.")
    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Check a training file for sentences that appear in the locked test sets."
    )
    parser.add_argument("training_file", help=".jsonl, .csv or .tsv")
    parser.add_argument(
        "test_file", nargs="?",
        help="one test file; default is every file in data/test_locked/",
    )
    parser.add_argument(
        "--columns", help="comma-separated column names to read from the test file",
    )
    parser.add_argument("--threshold", type=float, default=0.8, help="near-duplicate overlap (default 0.8)")
    parser.add_argument(
        "--min-words", type=int, default=5,
        help="matches shorter than this are reported but do not fail the check (default 5)",
    )
    parser.add_argument(
        "--reachable", action="append", metavar="FILE",
        help="text this training file was allowed to use, e.g. data/raw/barec/train.csv. "
             "Matches that also appear there are the corpus duplicating itself, not leakage. "
             "Repeatable.",
    )
    args = parser.parse_args()

    columns = args.columns.split(",") if args.columns else None
    test_files = [Path(args.test_file)] if args.test_file else locked_test_files()

    training_sentences = load_sentences(args.training_file)
    print(f"Training file:  {args.training_file}  ({len(training_sentences)} sentences)")

    reachable: list[str] = []
    for reachable_file in args.reachable or []:
        reachable += load_sentences(reachable_file)
    if reachable:
        print(f"Reachable text: {len(reachable)} sentences the training file may legitimately contain")

    total_real = 0
    total_short = 0

    for test_file in test_files:
        test_sentences = load_sentences(test_file, columns)
        exact, near = check_leakage(training_sentences, test_sentences, args.threshold)

        matches: list[tuple[str, str, float | None]] = [
            (train, test, None) for train, test in exact
        ]
        matches += [(train, test, score) for train, test, score in near]
        real = [m for m in matches if is_substantive(m[0], m[1], args.min_words)]
        short = [m for m in matches if not is_substantive(m[0], m[1], args.min_words)]
        real, explained = subtract_reachable(real, reachable, args.threshold)
        total_real += len(real)
        total_short += len(short)

        print(f"\n=== vs {test_file.name} ({len(test_sentences)} sentences) ===")
        print(f"Matches of {args.min_words}+ words: {len(real)}   <-- what counts as leakage")
        print(f"Shorter matches:      {len(short)}   (corpus noise — see --min-words)")
        if reachable:
            print(f"Also in reachable text: {explained}   (the corpus duplicating itself)")
        for train_sentence, test_sentence, score in real[:10]:
            kind = "exact" if score is None else f"{score:.3f}"
            print(f"  [{kind}] {train_sentence}  <->  {test_sentence}")
        if len(real) > 10:
            print(f"  ... and {len(real) - 10} more")

    if total_real:
        print(
            f"\nLEAKAGE DETECTED — {total_real} matches of {args.min_words}+ words. "
            f"This training file must not be used until it is fixed."
        )
        sys.exit(1)
    print(f"\nNo leakage found. ({total_short} short matches ignored — see --min-words.)")


if __name__ == "__main__":
    main()
