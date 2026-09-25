"""Smoke tests for lexical_scorer.py. Run with: uv run python scripts/test_lexical_scorer.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexical_scorer import LexicalScorer, normalize, stems


def test_text_returns_sane_shape():
    ls = LexicalScorer()
    mean_aoa, mean_zipf, n_words = ls.text("هذا كتاب جميل.")
    assert n_words > 0
    assert 1.0 <= mean_aoa <= 7.0, mean_aoa
    assert mean_zipf > 0, mean_zipf


def test_common_word_easier_than_rare_word():
    """A frequent, early-acquired word should score as easier (lower AoA, higher Zipf) than a rare,
    technical one -- the direction the whole ease_score formula depends on being right."""
    ls = LexicalScorer()
    common_aoa, common_zipf, _ = ls.text("بيت")  # "house" -- common, early-acquired
    rare_aoa, rare_zipf, _ = ls.text("استروبوسكوبي")  # a rare technical/loan term, unlikely to be rated
    assert common_zipf > rare_zipf, (common_zipf, rare_zipf)


def test_empty_text():
    ls = LexicalScorer()
    mean_aoa, mean_zipf, n_words = ls.text("")
    assert n_words == 0


def test_normalize_strips_definite_article():
    assert normalize("الكتاب") == "كتاب"
    assert normalize("كتاب") == "كتاب"  # no article, unchanged


def test_stems_includes_bare_token():
    assert "كتاب" in stems("كتاب")


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
