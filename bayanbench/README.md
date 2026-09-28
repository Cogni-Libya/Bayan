# BayanBench

Scores Arabic rewriting for dyslexic readers: does the rewrite keep the meaning, make the text easier, leave alone
what must not change, and survive real selections (cut-offs, messy text, long sentences)? Every measure is reported on
its own, with a 95% interval, on four item sets: **core** (BAREC), **held-out** (news, legal), **outside** (real text
from outside BAREC and SAMER) and **written** (medicine leaflets). There is no overall score. What each measure means,
and where the benchmark stops, is in the data card (`CARD.md` in the data repo).

- Data (private): Hugging Face dataset `Congi-libya/bayanbench-data`
- Leaderboard and human rating (private): Space `Congi-libya/bayanbench`

## Install

Python 3.10+, on Windows, Linux or Kaggle.

```bash
pip install "bayanbench[ease] @ git+https://github.com/Cogni-Libya/Bayan.git@main#subdirectory=bayanbench"
hf auth login        # once; a Hugging Face token with read access to Congi-libya (Kaggle: add HF_TOKEN as a secret)
bayanbench verify    # downloads the data and checks it against its checksums
```

Extras: `[ease]` reading level (torch, transformers), `[predict]` run a Hugging Face model, `[judge]` judge with an
API. Without `[ease]`, add `--no-level` to `score`. On Kaggle, the private GitHub repo needs a token:
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
3. **Leaderboard.** Upload the predictions file in the Space. Declare whether your training data had news or legal
   text (that decides whether the held-out set is really held out for your model).

**dev** is for choosing between models and checkpoints. **test** is run once per final model; test submissions are
logged on the leaderboard.

## Two tiers

- **Code tier**: deterministic checks (numbers, negations, clause length, easy text left unchanged, cut-off endings,
  protected text, house rules, hard words, reading level). Same outputs, same numbers, anywhere.
- **Judge tier**: track pass rates that need a meaning / Arabic-quality verdict. Verdicts are shared data in the data
  repo, keyed by the (selection, output) pair. Scoring never calls a judge: outputs already judged score at once,
  outputs nobody has judged yet are reported as **pending**, never guessed.

## Getting pending outputs judged

Judging needs access to the official judge (Gemini 3.1 Pro, v2 checklist prompt). Whoever holds it:

```bash
bayanbench pending preds_dev.jsonl -o pending.jsonl                      # outputs without an accepted verdict
bayanbench judge pending.jsonl --backend gemini --model <Gemini 3.1 Pro id> -o new_verdicts.jsonl
hf upload Congi-libya/bayanbench-data new_verdicts.jsonl verdicts/<date>_<who>.jsonl --repo-type dataset
```

A verdict counts only if its judge is in the data's `manifest.json` (`accepted_judges`). A new judge (another API,
an open model behind `--backend openai --base-url ...`) is accepted only if its verdicts on `judge/validation.jsonl`
pass `bayanbench validate-judge` against the thresholds in the manifest, which were set before any candidate was
tested.

## Development

```bash
pip install -e ".[dev]" && pytest -q tests        # tests use a tiny built-in dataset, no private data
```
