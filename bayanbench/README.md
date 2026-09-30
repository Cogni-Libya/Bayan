# BayanBench

Scores Arabic rewriting for dyslexic readers: does the rewrite keep the meaning, make the text simpler, leave alone
what must not change, and survive real selections? Every measure is reported on its own, with a 95% interval, on
four item sets: **core** (BAREC), **held-out** (news, legal), **outside** (real text from outside BAREC and SAMER)
and **written** (medicine leaflets). The data card (`CARD.md` in the data repo) says what each measure means and where
the benchmark stops.

- Data (private): Hugging Face dataset `Congi-libya/bayanbench-data`

**v2 (#48, in progress).** Meaning comes from an open scorer run locally (Gemma 4 31B int4 in scoring mode, #47)
instead of the Gemini judge; "simpler" is measured as continuous changes; the v1 measures are kept as diagnostics
until the human rating round decides which to drop. The meaning threshold, the flag threshold and the joint rate are
frozen from that round; until then the scorecard shows P(same meaning) and says the threshold is not frozen.

## Install

Python 3.10+, on Windows, Linux or Kaggle.

```bash
pip install "bayanbench[ease] @ git+https://github.com/Cogni-Libya/Bayan.git@main#subdirectory=bayanbench"
hf auth login        # once; a Hugging Face token with read access to Congi-libya (Kaggle: add HF_TOKEN as a secret)
bayanbench verify    # downloads the data and checks it against its checksums
```

Extras: `[ease]` reading level (torch, transformers), `[predict]` run a Hugging Face model, `[meaning]` score
meaning (vLLM, a 44 GB+ GPU), `[judge]` the v1 Gemini judge. Without `[ease]`, add `--no-level` to `score`. On Kaggle, the private GitHub repo needs a token:
`pip install "bayanbench[ease] @ git+https://$GITHUB_TOKEN@github.com/Cogni-Libya/Bayan.git@main#subdirectory=bayanbench"`.

## Score a model

1. **Outputs.** For a Hugging Face seq2seq model, run it the way the app runs it (sentence pieces, the app's guards):
   ```bash
   bayanbench predict --model Congi-libya/bayan-model2-arabart --prefix "بسط: [S2] " --split dev -o preds_dev.jsonl
   ```
   Any other system: write one line per item, `{"id": "<item id>", "output": "<the text the reader sees>"}`, for
   every item of the split (items are in `items/dev.jsonl` of the data repo).
2. **Scorecard.**
   ```bash
   bayanbench score preds_dev.jsonl --samer path/to/samer-simplification-corpus-v1 --json scores.json
   bayanbench score preds_dev.jsonl --baseline other_dev.jsonl        # paired differences on the same items
   ```
   `--samer` (your licensed SAMER copy, read once and cached) turns on the hard-word measures; without it they are
   reported as not measured. The reference submissions (copy, the shipped app, model 2) are in `baselines/dev/`.
3. **Declare** whether your training data had news or legal text: that decides whether the held-out set is really
   held out for your model.

**dev** is for choosing between models and checkpoints. **test** is run once per final model; test submissions are
logged on the leaderboard.

## What the scorecard shows

| block | measures | how |
|---|---|---|
| **meaning** | P(same meaning); **meaning kept** (P(same) ≥ frozen threshold, every number kept, no flagged contradiction) | open scorer, from shared scores |
| **simpler** | longest clause: words shorter · reading level: levels lower · hard words: fewer | change from selection to output, each on the selections that have something to simplify |
| **checks** | numbers kept · no house-rule break | code |
| **behaviour** | C easy text unchanged · F protected text · E1 cut-off ending kept | code, outside the headline |
| **flags** | negation / limit / condition changed | code; never a failure on its own: a flagged pair fails "meaning kept" only if the scorer's P(contradict) is over its threshold |
| **diagnostics** | kept 60%+ of words · no clause over 15 words · negations kept · mid-sentence full stop added | the v1 measures under test |

A punctuation-only edit (the same words in the same order) never counts as simpler in the joint rate: a comma is a
clause boundary, so it would shorten the longest clause without simplifying anything.

## Meaning scores are shared data

The scorer needs a GPU with 44 GB or more, so scoring never runs it. Scores live in `meaning/*.jsonl` of the data
repo, one record per (selection, output) pair, found by content: an output someone has already scored scores at once,
an output nobody has scored yet is reported as **pending**, never guessed. A meaning rate is shown only once 90% of its
items are scored. Copies of the selection need no scorer. Whoever has the GPU:

```bash
bayanbench meaning-pending preds_dev.jsonl -o pending.jsonl
bayanbench meaning pending.jsonl -o new_scores.jsonl          # pip install "bayanbench[meaning]" (vLLM)
hf upload Congi-libya/bayanbench-data new_scores.jsonl meaning/<date>_<who>.jsonl --repo-type dataset
```

The prompt is the meaning judge's teacher prompt (`scripts/meaning_judge/label_teacher.py`), so scores made with that
script are the same scores. For your own analysis, `score` takes `--meaning-threshold`, `--contradict-threshold` and
`--simpler-min CLAUSE_WORDS,LEVELS` (with `--joint`); the output then says the thresholds are yours.

## v1 judge tier (optional)

`bayanbench score --gemini` adds the v1 track pass rates from the shared Gemini 3.1 Pro verdicts; `pending`, `judge`
and `validate-judge` still work for it. The v1 Space app (`space/`) reads the v1 scorecard and has not been ported.

## Development

```bash
pip install -e ".[dev]" && pytest -q tests        # tests use a tiny built-in dataset, no private data
```
