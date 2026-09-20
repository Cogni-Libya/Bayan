"""
Leakage check for Bayan.

Usage:
    uv run python scripts/check_leakage.py <training_file.jsonl>

Checks a training file's sentences against every locked test sentence,
looking for exact matches and near-duplicates. Exits with an error if
anything is found.
"""
import json
import re
import string
import sys

# Diacritics — same set as score.py
_ARABIC_DIACRITICS = re.compile(
    r"[\u0610-\u061A\u064B-\u065F\u06D6-\u06DC\u06DF-\u06E8\u06EA-\u06ED\u08D4-\u08E1\u08E3-\u08FF]"
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

def load_sentences(path: str, field: str = "source") -> list[str]:
    """Load sentences from a JSONL file, one per line, from the given field."""
    sentences = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            sentences.append(row[field])
    return sentences


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

def char_ngrams(text: str, n: int = 5) -> set[str]:
    """Character n-grams of normalized text, for overlap comparison."""
    if len(text) < n:
        return {text}
    return {text[i:i + n] for i in range(len(text) - n + 1)}


def ngram_overlap(a: str, b: str, n: int = 5) -> float:
    """Jaccard overlap between two strings' character n-gram sets."""
    ngrams_a = char_ngrams(a, n)
    ngrams_b = char_ngrams(b, n)
    if not ngrams_a or not ngrams_b:
        return 0.0
    intersection = len(ngrams_a & ngrams_b)
    union = len(ngrams_a | ngrams_b)
    return intersection / union


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
    normalized_test = [normalize(t) for t in test_sentences]
    test_set = set(normalized_test)

    exact_matches = []
    near_duplicates = []

    for train_sent in training_sentences:
        norm_train = normalize(train_sent)

        if norm_train in test_set:
            exact_matches.append(train_sent)
            continue  # an exact match is also a near-duplicate; don't double count

        for norm_test, orig_test in zip(normalized_test, test_sentences):
            overlap = ngram_overlap(norm_train, norm_test)
            if overlap >= overlap_threshold:
                near_duplicates.append((train_sent, orig_test, overlap))

    return exact_matches, near_duplicates


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def main(training_file: str, test_file: str) -> None:
    training_sentences = load_sentences(training_file)
    test_sentences = load_sentences(test_file)

    print(f"Training sentences: {len(training_sentences)}")
    print(f"Test sentences:     {len(test_sentences)}")

    exact, near = check_leakage(training_sentences, test_sentences)

    print(f"\nExact matches:    {len(exact)}")
    for e in exact[:10]:
        print(f"  {e}")
    if len(exact) > 10:
        print(f"  ... and {len(exact) - 10} more")

    print(f"\nNear-duplicates:  {len(near)}")
    for train_sent, test_sent, score in near[:10]:
        print(f"  {score:.3f}: {train_sent}  <->  {test_sent}")
    if len(near) > 10:
        print(f"  ... and {len(near) - 10} more")

    if exact or near:
        print("\nLEAKAGE DETECTED — training file must not be used until fixed.")
        sys.exit(1)
    else:
        print("\nNo leakage found.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run python scripts/check_leakage.py <training_file.jsonl> <test_file.jsonl>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])