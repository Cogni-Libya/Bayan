"""
Leakage check for Bayan.

Usage:
    uv run python scripts/check_leakage.py <training_file>              # against every locked test set
    uv run python scripts/check_leakage.py <training_file> <test_file>  # against one

Compares a training file's sentences against the locked test sentences, looking for
exact matches and near-duplicates. Exits with an error if anything is found.

Reads .jsonl, .csv and .tsv, and compares every column that holds sentences. For the
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

LOCKED_DIR = Path(__file__).resolve().parent.parent / "data" / "test_locked"

# Every one of these that a file actually has is read. Covers our generated-pairs
# format, the scoring format, BAREC (Sentence) and SAMER (L5/L4/L3).
TEXT_COLUMNS = (
    "original_text", "simplified_text",
    "source", "target", "prediction",
    "Sentence", "L5", "L4", "L3", "text",
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
    """Read a .jsonl, .csv or .tsv file into a list of dicts.
    utf-8-sig because BAREC's CSV ships with a byte-order mark."""
    suffix = path.suffix.lower()
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
        f"{path}: unsupported file type '{suffix}'. Expected .jsonl, .csv or .tsv."
    )


def load_sentences(path: str | Path, columns: list[str] | None = None) -> list[str]:
    """Load every sentence from a file, taking all the text columns it has."""
    path = Path(path)
    rows = _read_rows(path)
    if not rows:
        return []

    wanted = columns or TEXT_COLUMNS
    present = [c for c in wanted if c in rows[0]]
    if not present:
        raise SystemExit(
            f"{path}: no sentence column found. This file has: {sorted(rows[0])}. "
            f"Name the right one with --columns."
        )

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


def check_leakage(
    training_sentences: list[str],
    test_sentences: list[str],
    overlap_threshold: float = 0.8,
) -> tuple[list[str], list[tuple[str, str, float]]]:
    """
    Compare every training sentence against every test sentence.
    Returns (exact_matches, near_duplicates).
    near_duplicates is a list of (train_sentence, test_sentence, overlap_score).
    """
    test_normalized = [normalize(t) for t in test_sentences]
    test_ngrams = [char_ngrams(t) for t in test_normalized]
    test_exact = set(test_normalized)

    exact_matches = []
    near_duplicates = []

    for train_sentence in training_sentences:
        norm_train = normalize(train_sentence)

        if norm_train in test_exact:
            exact_matches.append(train_sentence)
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
    args = parser.parse_args()

    columns = args.columns.split(",") if args.columns else None
    test_files = [Path(args.test_file)] if args.test_file else locked_test_files()

    training_sentences = load_sentences(args.training_file)
    print(f"Training file:  {args.training_file}  ({len(training_sentences)} sentences)")

    total_exact = 0
    total_near = 0

    for test_file in test_files:
        test_sentences = load_sentences(test_file, columns)
        exact, near = check_leakage(training_sentences, test_sentences, args.threshold)
        total_exact += len(exact)
        total_near += len(near)

        print(f"\n=== vs {test_file.name} ({len(test_sentences)} sentences) ===")
        print(f"Exact matches:    {len(exact)}")
        for e in exact[:10]:
            print(f"  {e}")
        if len(exact) > 10:
            print(f"  ... and {len(exact) - 10} more")

        print(f"Near-duplicates:  {len(near)}")
        for train_sentence, test_sentence, score in near[:10]:
            print(f"  {score:.3f}: {train_sentence}  <->  {test_sentence}")
        if len(near) > 10:
            print(f"  ... and {len(near) - 10} more")

    if total_exact or total_near:
        print(
            f"\nLEAKAGE DETECTED — {total_exact} exact, {total_near} near-duplicate. "
            f"This training file must not be used until it is fixed."
        )
        sys.exit(1)
    print("\nNo leakage found.")


if __name__ == "__main__":
    main()
