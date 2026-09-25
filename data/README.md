# Data

Raw and processed data files are git-ignored (large, and easy to regenerate) — this note
is so anyone on the team can get them back.

## BAREC corpus (`data/raw/barec/{train,dev,test}.csv`)

Source: [`CAMeL-Lab/BAREC-Shared-Task-2025-sent`](https://huggingface.co/datasets/CAMeL-Lab/BAREC-Shared-Task-2025-sent)
on Hugging Face — confirmed public (not gated), **CC-BY-SA 4.0**, no registration
required to download. The shared-task GitHub repo
([`CAMeL-Lab/barec-shared-task-2025`](https://github.com/CAMeL-Lab/barec-shared-task-2025))
only has eval scripts (MIT) plus a Google Form; that form registers you for the
*competition leaderboard*, it is not needed just to get the corpus.

69,441 sentences total (train 54,845 / dev 7,310 / test 7,286 minus headers), each
labeled at four readability granularities (19 / 7 / 5 / 3 levels), with `Domain`,
`Source`, `Text_Class`, and `Annotator` metadata — **not a parallel
simplification corpus** (no aligned complex/simple rewrites), same role as
already designed in the pipeline report: real "complex" source sentences plus a
calibrated readability signal for QC.

Re-download with:

```bash
mkdir -p data/raw/barec
for f in train dev test; do
  curl -sL "https://huggingface.co/datasets/CAMeL-Lab/BAREC-Shared-Task-2025-sent/resolve/main/$f.csv" \
    -o "data/raw/barec/$f.csv"
done
```

## Processed (`data/processed/`)

The cleaned corpus (columns kept, level 5 dropped) is no longer a standalone file --
`load_and_clean_barec()` in `scripts/barec_simplification_pipeline.py` reads directly from
`data/raw/barec/*.csv` and does this in-memory, every run. There's nothing to regenerate or
keep in sync; if you need the cleaned DataFrame standalone, call that function.

Everything else under `data/processed/` is real output, not intermediate scratch, and none of
it is regenerable from the corpus alone -- most of it required real API or GPU spend to
produce:

- `barec_hard_pilot_raw_results.parquet`, `barec_simplification_pilot.parquet`,
  `barec_hard_pilot_checkpoint.jsonl` -- the main pipeline's pilot run output and its
  resume checkpoint (see `barec_simplification_pipeline.py`).
- `marbert_full_corpus_predictions.parquet` -- the production ONNX MARBERT level
  classifier run over the entire 67,601-sentence corpus (see the `level-classifier-benchmark`
  memory note), split into held-out/train-seen views. MARBERT was replaced by CAMeL AraBERT as the
  readability check in #17; the script that produced this file, `run_marbert_full_corpus.py`, was
  removed then and is in the git history before that change.
- `*_eval_results.parquet` -- per-example predictions from the various classifier/validator
  benchmarking runs (see the `level-classifier-benchmark` memory note for what each one is).
- `data/processed/archive/` -- superseded checkpoints and results kept for reference, not
  deleted outright when a design changed underneath them.
- `data/annotations/equivalence_and_level_annotations.json` -- human verdicts pulled from
  the "Pilot Pair Review" Claude Artifact's shared database (not live; re-pull for a fresher
  snapshot). Read by `optimize_equivalence_validator.py` to build MIPROv2 training/held-out
  data; real ground truth, not regenerable.
- `readability_compare_inputs/samer_test.parquet` -- the real, full-sentence SAMER evaluation
  set: the official test split's own `Novel`/`Chapter`/`L5`/`L4`/`L3` structure (3,277 rows;
  1,678 where `L5 != L3`, i.e. where a genuine simplification exists at that gap). This is the
  correct artifact for "does this signal rank a real human simplification above its harder
  source" -- confirmed by genuine word-count variance between L5 and L3 (ratio SD 0.056).
  Used to fit and validate `EASE_W_CAMEL_LOGIT`/`EASE_W_MEAN_AOA` in
  `barec_simplification_pipeline.py` (see `pipeline_architecture.tex` Section 4).
- `readability_compare_inputs/samer_pairs.parquet` -- **not** a full-sentence dataset despite
  an earlier session describing it that way: every one of its 7,754 rows is a *minimal
  single-word-substitution* pair (built by `build_samer_minimal_pairs.py`; every row carries
  `orig_word`/`new_word`, and word count is byte-identical between `original_text` and
  `modified_text` on literally every row -- confirmed by a zero-variance ratio check). Real
  data, not wrong -- just a different, narrower task: which of two candidate *words* is the
  easier substitute, not which of two *sentences* reads easier. Legitimate as a lexical
  word-choice eval (AoA discriminates it well; word length carries a real but
  sentence-rewriting-irrelevant residual-difficulty signal there -- a suppression effect, not
  noise). Do not use for sentence-level readability/reranking validation; that mistake is what
  produced the wrong `ease_score` formula version this file note exists to prevent recurring.

Also not under `data/`: `models/level_classifier_bert_marbert_onnx_int8/` (the former production
quantized MARBERT weights, ~164MB, replaced by CAMeL AraBERT in #17; no code loads it any more) is
git-ignored (see `.gitignore`) and real trained output, not source-controlled -- see the
`level-classifier-benchmark` memory note for how to regenerate it. The current readability model
needs no manual download: `models/camel_readability_arabertv02_word_onnx/` (git-ignored, ~520MB) is
created on first use by `scripts/camel_readability.py`. `scripts/compiled/*.json` (DSPy-optimizer-compiled generator/validator
programs) are small enough to commit and are not git-ignored.
