# Copy baseline: SAMER test

Date: 2026-09-21
Set: SAMER test split (3,277 rows), locked, unmodified
Scoring: `scripts/evaluation/score.py`, SARI via huggingface/evaluate

Commands:
```
python scripts/evaluation/make_eval_input.py --format samer --input data/test_locked/samer_test.tsv --output samer_copy.jsonl --expected-rows 3277
python score.py samer_copy.jsonl
```

Note: the MODEL and COPY BASELINE sections are identical because the predictions are the source. This is expected, not a bug.

Note: 1,599 of 3,277 rows (48.8%) have L5 == L3, so overall SARI is lifted by the unchanged bucket. The bar a model has to clear is the Changed references SARI.

```
Loaded 3277 rows (1678 changed, 1599 unchanged, 0 no references)

--- Overall (n=3277) ---
Copy rate:        1.000
SARI:             77.499
BLEU:             72.033
BERTScore:        1.000
Readability drop: 0.000

--- Changed references (n=1678) ---
Copy rate:        1.000
SARI:             56.057
BLEU:             59.104
BERTScore:        1.000
Readability drop: 0.000

--- Unchanged references (n=1599) ---
Copy rate:        1.000
SARI:             100.000
BLEU:             100.000
BERTScore:        1.000
Readability drop: 0.000

--- No references (n=0) ---
(no rows)
```

# Copy baseline: BAREC test

Date: 2026-09-21
Set: BAREC test split (7,286 rows), locked, unmodified
Scoring: `scripts/evaluation/score.py`, SARI via huggingface/evaluate

Commands:
```
python scripts/evaluation/make_eval_input.py --format barec --input data/test_locked/barec_test.csv --output barec_copy.jsonl --expected-rows 7286
python score.py barec_copy.jsonl
```

Note: BAREC has no gold simplifications, so every row lands in "No references." SARI and BLEU are undefined (nan) there by design — only the reference-free metrics (BERTScore, readability drop) apply. The MODEL and COPY BASELINE sections are identical because the predictions are the source; this is expected, not a bug.

```
Loaded 7286 rows (0 changed, 0 unchanged, 7286 no references)

--- No references (n=7286) ---
Copy rate:        1.000
SARI:             nan
BLEU:             nan
BERTScore:        1.000
Readability drop: 0.000
```