# SAMER Model — Dev Results

Model: `UBC-NLP/AraT5v2-base-1024` (fine-tuned)
Seed: `42`

## Dev metrics (best checkpoint by eval_sari, scored on FULL dev — 2,983 rows)

| Metric | Value |
| --- | --- |
| SARI | 77.06 |
| BLEU | 0.7316 |
| Copy rate | 66.51% |

> **Read with the copy baseline.** Returning every sentence unchanged scores SARI **74.25** on the same
> 2,983 rows, because 41% of dev is sentences the humans left alone. The model's real gain is on the
> 1,754 rows people simplified: **63.66 vs 56.21** for copying (+7.46). Added 24 Sep when this file
> moved from the repo root to `docs/`.
| Eval loss | 0.4808 (logged for visibility only — not used to select the checkpoint) |

Best checkpoint reached at step 3000 of 3250 (epoch ~9 of 10).

## Methodology notes

* Checkpoint selection: early stopping and best-checkpoint selection used
`eval_sari`, not `eval_loss`, per mentor guidance. Dev is SAMER's own split
with ~43% identity pairs, so loss alone would favor a model that leans
toward copying its input.
* Training-time evaluation: SARI/BLEU/copy-rate were computed on a fixed
500-row random subset of dev (seed 42) at every eval step, to keep training
fast. The numbers above are from a single full-dev evaluation (2,983 rows)
run once at the end, using the best checkpoint.
* Splits: SAMER's own official train/dev/test split was used as
downloaded — no re-splitting was done. Dev and test were not
identity-capped (unlike train, capped at 20%): they keep every row,
including sentences that need no change, since a real user will paste
sentences that are already easy and the model has to leave those alone.
Knowing when not to simplify is part of the task.

## Known limitation (manual spot-check)

Manual review of a small sample of predictions found the model tends to
make conservative (partial) simplifications — substituting a single word
rather than rephrasing the full sentence — and at least one meaning-altering
substitution error was found ("عزلة" [isolation] → "استعباد" [enslavement]).
Automatic scores (SARI/BLEU) do not catch this class of error. This is
expected given SAMER's limited size (~10K training pairs after
identity-capping) and its literary, archaic vocabulary.

A separate, larger ad-hoc check on a handful of hand-picked sentences
initially looked concerning (5/5 unchanged), but this turned out to be a
sampling artifact, not a model or tokenizer defect: with an overall copy
rate of ~66.5%, a small random sample landing entirely in the "unchanged"
category is expected roughly 1 in 8 times. The full `dev_predictions.csv`
(2,983 rows) is the reliable source for spot-checking, not small hand-built
samples — a useful reminder for anyone reviewing this model or the next one.

## Domain note

This model is trained and evaluated entirely on SAMER (literary/novel
text). Our target application domain is general/news text. Performance on
out-of-domain input has not yet been systematically tested — this is a key
comparison point for the second model (trained on our synthetic data).

## Artifacts

* Checkpoint: `Congi-libya/samer-arat5v2-base-simplification` (Hugging Face, team org)
* Training notebook: `scripts/training/model1_training.ipynb`
* Full dev predictions (`ID, original_text, reference, prediction`): kept on Kaggle, **not in the
  repo**. They contain SAMER sentences, and SAMER's licence forbids redistributing its text.