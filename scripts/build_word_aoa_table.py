"""Turn rate_words_llm.py's ratings checkpoint into the AoA table LexicalScorer reads.

Each checkpoint line holds one (sample, batch) of ratings: {"sample", "batch", "ratings": [[word, 1-7], ...]}.
A word's aoa_llm is the mean over all its samples; n_ratings records how many there were.

    uv run python scripts/build_word_aoa_table.py RATINGS.jsonl [data/processed/word_aoa/word_aoa_llm.parquet]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lexical_scorer import AOA_PATH  # noqa: E402


def build(ratings_path: Path) -> pl.DataFrame:
    scores: dict[str, list[int]] = defaultdict(list)
    with open(ratings_path, encoding="utf-8") as f:
        for line in filter(str.strip, f):
            for word, rating in json.loads(line)["ratings"]:
                scores[word].append(rating)
    words = sorted(scores)
    return pl.DataFrame({
        "word": words,
        "aoa_llm": [sum(scores[w]) / len(scores[w]) for w in words],
        "n_ratings": [len(scores[w]) for w in words],
    })


if __name__ == "__main__":
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else AOA_PATH
    table = build(Path(sys.argv[1]))
    out.parent.mkdir(parents=True, exist_ok=True)
    table.write_parquet(out)
    print(f"wrote {table.shape[0]} words to {out}")
