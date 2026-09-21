# Pipeline check: predict.py + score.py end-to-end

Date: 2026-09-21
Purpose: pipeline test only. Not a baseline, not for the Action Plan.
Model: UBC-NLP/AraT5v2-base-1024, zero-shot (untrained checkpoint), greedy decoding
Set: SAMER dev, random 200-row sample (seed 0), never the locked test set

Note: transformers 5.0.0 fails to load AraT5v2's tokenizer (`KeyError: 0` in
tokenizer conversion). Pinning `transformers==4.46.3` fixes it. Filed as a
finding.

```
Loaded 200 rows (112 changed, 88 unchanged, 0 no references)

--- Overall (n=200) ---
Copy rate:        0.010
SARI:             22.642
BLEU:             0.456
BERTScore:        0.644
Readability drop: 3.948
```

Confirms: pipeline runs end to end; every metric produces a non-trivial
number on real model output (unlike the copy baseline, where SARI/BLEU/
BERTScore/readability drop are trivially 100/100/1.0/0). No new bugs beyond
the "No references" bucket, already fixed in this PR.