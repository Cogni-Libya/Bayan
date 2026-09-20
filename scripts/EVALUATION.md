# Evaluation scripts

## score.py

Scores a model's predictions against SARI, BLEU, BERTScore, readability drop,
and copy rate — reported overall, and separately for changed vs unchanged
reference rows, alongside a copy-the-input baseline.

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
uv run python scripts/check_leakage.py <training_file.jsonl> <test_file.jsonl>
```

**Example:**
```bash
uv run python scripts/check_leakage.py scripts/toy_train.jsonl scripts/toy_test.jsonl
```

Exits with code 1 and prints details if any exact match or near-duplicate
(character 5-gram overlap ≥ 0.8) is found.

## make_manifest.py

Regenerates `data/test_manifest.json` from the files in `data/test_locked/`.
Only needed if the locked test files change.

```bash
uv run python scripts/make_manifest.py
```

## Locked test sets

The real test files live in `data/test_locked/` and are **never committed**
(see `.gitignore`). `data/test_manifest.json` records each file's row count
and SHA-256 hash, so anyone can confirm they're scoring the same data without
the files themselves being shared or version-controlled.