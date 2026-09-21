# Evaluation scripts

## score.py

Scores a model's predictions against SARI, BLEU, BERTScore, readability drop,
and copy rate — reported overall and then in three buckets, alongside a
copy-the-input baseline.

The three buckets are:

| Bucket | Meaning | What a good model does |
|---|---|---|
| **Changed references** | a human simplified this sentence | simplify it too |
| **Unchanged references** | a human left it alone | leave it alone |
| **No references** | we have no gold simplification, so we can't say | judged on the reference-free metrics only |

BAREC has no gold simplifications, so every BAREC row lands in **No references** —
not in "unchanged". SARI and BLEU are skipped for that bucket rather than reported
as `nan`.

**Input format** — one JSON object per line:
```json
{"id": "1", "source": "...", "prediction": "...", "references": ["...", "..."]}
```
`references` may be an empty list (e.g. for BAREC, which has no gold simplifications).

**Usage:**
```bash
uv run python scripts/score.py <predictions.jsonl>
```

**Example:**
```bash
uv run python scripts/score.py scripts/toy_predictions.jsonl
```

SARI is computed with `evaluate`'s implementation (see `SARI_IMPLEMENTATION`
constant in the script) — pinned so results can't silently drift if a
different library version changes its formula.

## check_leakage.py

Checks whether any sentence in a training file matches — exactly or nearly —
a sentence in a locked test file. Normalizes text first (strips diacritics
and punctuation, unifies alef/ta-marbuta/ya forms) so spelling variants don't
hide a real duplicate.

**Usage:**
```bash
# against every file in data/test_locked/ — this is the one to run
uv run python scripts/check_leakage.py <training_file>

# or against a single test file
uv run python scripts/check_leakage.py <training_file> <test_file>
```

**Example:**
```bash
uv run python scripts/check_leakage.py scripts/toy_train.jsonl scripts/toy_test.jsonl
```

Reads `.jsonl`, `.csv` and `.tsv` on both sides, and compares **every column that
holds sentences** — so for SAMER that is `L5`, `L4` and `L3` together, because a
simplified target that reappears in training is leakage just as much as a source
sentence is. Columns are auto-detected (`original_text`, `simplified_text`,
`source`, `target`, `Sentence`, `L5`, `L4`, `L3`, `text`); override with
`--columns`, and the near-duplicate threshold with `--threshold`.

Exits with code 1 if any exact match or near-duplicate (character 5-gram overlap
≥ 0.8) survives the two filters below.

### Two filters, and why they exist

**`--min-words` (default 5).** BAREC is sentence-level and full of one- and
two-word rows — 797 of its 7,286 test rows are ≤ 2 words. Those match everything.
Short matches are still counted and printed, they just don't fail the run.

**`--reachable FILE` (repeatable).** BAREC repeats **311 sentences between its own
train and test splits**, and more again as near-duplicates. So a pair generated
from a train row can reproduce a test sentence without anyone ever touching the
test split. Pass the splits the training file was allowed to use and those matches
are subtracted:

```bash
uv run python scripts/check_leakage.py data/processed/synthetic.jsonl \
    --reachable data/raw/barec/train.csv \
    --reachable data/raw/barec/dev.csv
```

Without this, **any** BAREC-derived training file fails the check, and a check
that always fails is a check everyone learns to ignore. With it, a failure means
something.

Expect roughly **2 minutes** for a 10,000-row training file against both locked
test sets, or **8 minutes** for the full 41,000-row synthetic export.

## make_manifest.py

Regenerates `data/test_manifest.json` from the files in `data/test_locked/`.
Only needed if the locked test files change.

```bash
uv run python scripts/make_manifest.py
```

## Locked test sets

The real test files live in `data/test_locked/` and are **never committed**
(see `.gitignore`). `data/test_manifest.json` records each file's row count,
SHA-256 hash and `source`, so anyone can confirm they're scoring the same data
without the files themselves being shared or version-controlled.

Both locked sets are the corpora's own official test splits, byte-for-byte
unmodified — we did not make our own split. So to reproduce them:

```bash
cp data/raw/barec/test.csv                                        data/test_locked/barec_test.csv
cp data/raw/samer/samer-simplification-corpus-v1/data/test.tsv    data/test_locked/samer_test.tsv
uv run python scripts/make_manifest.py     # hashes must match what is committed
```

`make_manifest.py` recomputes rows and hashes but **carries `source` over** from the
existing manifest, since a hash only proves two people hold the same bytes — it
says nothing about where those bytes came from. If you add a locked file, write its
`source` by hand.