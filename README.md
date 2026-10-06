<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/banners/bayan-banner-editorial-dark.png">
    <img src="docs/brand/banners/bayan-banner-editorial-light.png" alt="Bayan (بيان): اقرأ بوضوح. An AI Reading Assistant for Arabic Readers with Dyslexia" width="100%">
  </picture>
</p>

# Bayan (بيان) — An AI Reading Assistant for Arabic Readers with Dyslexia

**Team Cogni** · Samsung Innovation Campus (SIC) AI Course — Capstone Project

Bayan simplifies complex Arabic text for readers with dyslexia while preserving its meaning, then adds
diacritics and reads it aloud with synchronized word highlighting.

**Download:** [Bayan 2.1.0 for Android](https://bayan-android.vercel.app) (Android 8 or newer; APKs and SHA-256 on
[Hugging Face](https://huggingface.co/Congi-libya/Bayan-App)) · **Models:** [BayanSimplify](https://huggingface.co/Congi-libya)
on Hugging Face · Changelog: [`app/CHANGELOG.md`](app/CHANGELOG.md)

> This README replaces the original idea brief, which is kept for history in
> [`references/00_project_brief/original_project_brief.md`](references/00_project_brief/original_project_brief.md).
> Where the two disagree, this file and [`references/INDEX.md`](references/INDEX.md) are current.

---

## 1. The problem

Readers with dyslexia can see text but struggle to process it. Arabic adds specific barriers that most
(Latin-script) dyslexia tools do not address:

- **Missing diacritics (tashkeel):** everyday text omits short vowels, so pronunciation must be inferred from context.
- **Dense morphology:** prefixes and suffixes attach directly to words; reading-disabled Arabic-speaking children show
  early deficits in morphological awareness (Saiegh-Haddad & Taha, 2017).
- **Long, clause-chained sentences and low-frequency vocabulary.**

Scale: a meta-analysis of 18 studies (N = 30,243) estimates **11%** pooled prevalence of developmental dyslexia among
Arab primary-school children (Aldakhil, 2024). Dyslexia is not the same as low reading proficiency — never quote
PISA / learning-poverty figures as dyslexia rates.

Evidence from user studies (Spanish, Rello et al., 2013): **more frequent and shorter words** help readers with dyslexia,
and **offering simpler synonyms on demand** is preferred over silently replacing words. No deployed Arabic tool combines
simplification with a dyslexia focus; existing Arabic apps offer diacritization and read-aloud only.

All figures are verified in [`references/01_problem_motivation/`](references/01_problem_motivation/arabic_reading_and_dyslexia_evidence.md).

## 2. The solution — a three-stage pipeline

| Stage | What it does | Status |
|---|---|---|
| **1. Simplify (core)** | Shorten and restructure sentences, replace rare words, keep meaning | **In the app.** The **BayanSimplify** models run on the phone as int8 ONNX bundles: **BayanSimplify-v0.2-Fast** (AraBART, the default download, 222 MB) and **BayanSimplify-v0.3** (AraT5v2, the large model and our best, decoded with four beams, 471 MB); BayanSimplify-v0.2 stays available as the earlier large model |
| 2. Diacritize | Restore full tashkeel on the simplified text | **In the app** (the *Show tashkeel* setting). **Libtashkeel** (`text2tashkeel`): MIT, 4.8 MB, bundled with the app, never changes a letter |
| 3. Read aloud | TTS with word-by-word highlighting | **In the app.** **Nabra-7M-Distill** (int8, 8.7 MB) through sherpa-onnx, the spoken word highlighted; three Piper voices as optional downloads |

Order matters: simplify → diacritize → read aloud, because diacritics depend on the final wording.

### How it reaches the reader

Bayan is an **Android plugin**. It registers a `PROCESS_TEXT` intent, so «تبسيط» (Simplify) appears in the
text-selection menu of any app: the reader selects hard Arabic text where they meet it, and a panel over that app
streams the simplified version sentence by sentence, with the original one tap away. The panel can read aloud,
and minimizes to a floating reader so the reader can keep using the app while Bayan reads on. **All inference runs
on the device**: no server, no network, and the text never leaves the phone.

Before and after the model, a **text step** in code guards the output: scripture and set poetry pass through
untouched, very short sentences are left alone, and a rewritten sentence that drops a number or a Latin token,
changes a negation, limit or condition word, or loses too much of its text is replaced by the original sentence.

Constraints: ONNX Runtime Mobile only, no Python or GPU at runtime, and a default download within 250 MB
(BayanSimplify-v0.2-Fast, 222 MB); the AraT5v2 bundles (471 MB) are optional downloads, kept whole for quality. Reasoning: [`docs/decisions/0001-product-form.md`](docs/decisions/0001-product-form.md);
app build and layout: [`app/`](app/); brand, logo, colours and reading rules: [`app/design-system/`](app/design-system/readme.md).

### Demo

Recorded on a phone over an Arabic Wikipedia paragraph: select the text → **تبسيط** in the selection menu →
the simplified version in the bottom sheet, with read-aloud.

<video src="deliverables/05_demo/bayan_demo.mp4" controls width="320"></video>

Local copy: [`deliverables/05_demo/bayan_demo.mp4`](deliverables/05_demo/bayan_demo.mp4) — the same clip
runs in the pitch decks (`deliverables/04_presentation/`).

## 3. Data

No large, open, parallel Arabic simplification corpus fits the task, so Bayan builds its own:

- **Source sentences:** [BAREC](https://huggingface.co/datasets/CAMeL-Lab/BAREC-Shared-Task-2025-sent)
  (CAMeL Lab, 69,441 sentences, 19 readability levels, CC BY-SA 4.0, **not parallel**). See [`data/README.md`](data/README.md).
- **Synthetic corpus v1** ([`Congi-libya/bayan-simplification-corpus`](https://huggingface.co/datasets/Congi-libya/bayan-simplification-corpus),
  public, CC BY-SA 4.0; 14,975 rows): hard BAREC sentences rewritten by Gemma 4 31B, kept only if code checks pass,
  CAMeL rates the rewrite at least 2 levels easier, and a Qwen judge scores the meaning as kept; easy, protected and
  short sentences are kept verbatim. Pipeline: [`scripts/barec_simplification_pipeline.py`](scripts/barec_simplification_pipeline.py),
  [`scripts/assemble_corpus_v1.py`](scripts/assemble_corpus_v1.py); data card:
  [`docs/synthetic_data_card_v1.md`](docs/synthetic_data_card_v1.md). Corpus v0 (13,072 rows) is kept on the Hub under the tag `v0`.
- **SAMER** *is* used for training. CAMeL Lab approved fine-tuning on it and publishing the resulting weights for
  non-commercial use. Redistributing the corpus is **not** allowed: SAMER text must never be committed, pasted into an
  issue, or included in any deliverable.
- **BayanSimplify-v0.2 training data** (private, 22,733 pairs, for v0.2 and v0.2-Fast): SAMER L5→L3 (14,343), DAASI train (1,502) and Baseet (6,888,
  filtered for meaning), each source starting with a strength tag (`[S0]`–`[S3]`, `[SA]`). The app sends no tag, which
  keeps the meaning more often (see below).
- **BayanSimplify-v0.3** retrains AraT5v2 on corpus v1 ([`scripts/meaning_reward/`](scripts/meaning_reward/)); the meaning judge is in [`scripts/meaning_judge/`](scripts/meaning_judge/).
- **Leakage:** 9.3% of Baseet overlapped our locked test sets; every training file now passes
  [`scripts/evaluation/check_leakage.py`](scripts/evaluation/README.md). 33 BayanBench held-out items appear in corpus v1,
  so models trained on it are reported on the core and outside items only.

## 3a. The BayanSimplify models

Public on Hugging Face under CC BY-NC 4.0 (non-commercial, in line with the training data's terms):

| Model | Base | Training data | In the app |
|---|---|---|---|
| [BayanSimplify-v0.1](https://huggingface.co/Congi-libya/BayanSimplify-v0.1) | AraT5v2-base-1024 | SAMER, level 5 → 3 | not shipped |
| [BayanSimplify-v0.2](https://huggingface.co/Congi-libya/BayanSimplify-v0.2) | AraT5v2-base-1024 | 22,733-pair mix with strength tags | "Earlier large model" |
| [BayanSimplify-v0.2-Fast](https://huggingface.co/Congi-libya/BayanSimplify-v0.2-Fast) | AraBART | the same mix | "Fast model", the default download |
| [BayanSimplify-v0.3](https://huggingface.co/Congi-libya/BayanSimplify-v0.3) | AraT5v2-base-1024 | corpus v1 (14,975 rows) | "Large model", four beams; **our best** |
| [BayanSimplify-ONNX](https://huggingface.co/Congi-libya/BayanSimplify-ONNX) | | the int8 bundles the app downloads | `v0.2-Fast/`, `v0.2/`, `v0.3/` |

## 4. Results (internal, not peer-reviewed)

The full tables, intervals and figures are in the final report
([`deliverables/03_final_report/`](deliverables/03_final_report/)). On **BayanBench v2, test split, core items**
(meaning kept = Gemma 4 31B P(same) ≥ 0.5 and every number kept):

| System | Meaning kept | Longest clause, words shorter |
|---|---|---|
| copy the input | 100% | 0 |
| BayanSimplify-v0.2 (AraT5v2), `[S2]` / no tag | 59.5% / 68.3% | 6.3 / 4.5 |
| BayanSimplify-v0.2-Fast (AraBART), `[S2]` / no tag | 40.1% / 51.4% | 6.7 / 4.9 |
| app, v0.2 int8 / v0.2-Fast int8 (September text step) | 78.6% / 50.5% | 1.9 / 4.8 |
| **app, BayanSimplify-v0.3 int8, four beams** | **82%** | **5.2** |

- **Meaning and simplification trade off.** Within each architecture the tagged setting simplifies most and keeps the
  meaning least often; AraT5v2 keeps it 17–28 points more often than AraBART at the same setting.
- **BayanSimplify-v0.3 with four beams outperforms every earlier model** (#61, #68): it keeps the meaning more often
  than any of them and cuts 5.2 words from the longest clause; even against v0.2 behind the app's newest checks it is no
  worse on meaning and cuts about three times as many words. People agree: in a blind rating its changed outputs were
  found easier 86% of the time (v0.2: 60%), and every team vote between the two chose v0.3. It is the app's large model.
- **The scorer tracks people.** Five raters and a reader with dyslexia rated 290 outputs and comparisons: Gemma 4 31B
  separates outputs judged faithful from the rest with AUC 0.85 [0.78, 0.91]; only meaning was rated consistently
  enough to validate (α 0.51). The reader with dyslexia found 17 of 30 rewrites easier, 4 harder.
- **SARI is not enough.** Copying the input scores 77.5 SARI on SAMER test; BayanSimplify-v0.1 beats copying only on the rows
  people changed (+5.77) and learned one-word substitutions.
- **On the phone** (Xiaomi Mi 11X, Snapdragon 870): the first word of a rewrite appears 82–172 ms after the request
  with v0.2-Fast and 177–318 ms with the AraT5v2 models; v0.3 with four beams writes a sentence in about 1.2 s.

## 4a. BayanBench

[`bayanbench/`](bayanbench/) (v2.0, frozen; tag `bayanbench-v2.0`) scores a simplifier on 1,981 items (dev 731 /
test 1,250, split by document) in core, held-out, outside and written sets. It reports meaning, simplification
(clause length, CAMeL reading level, hard words), deterministic checks (numbers, house rules) and behaviour tests
(easy text left alone, protected text, cut-off selections), each with a document-bootstrap interval, and paired
differences against a baseline. No composite score. Data: `Congi-libya/bayanbench-data` (private, team only).

```bash
cd bayanbench && uv run bayanbench score outputs.jsonl --split dev --data <bayanbench-data snapshot>
```

## 5. Key insights from the literature review (2026-09-17)

Full details and sources: [`references/INDEX.md`](references/INDEX.md).

1. **Baseet's "best" hybrid is not better than plain AraT5v2.** Its headline score included training rows; on its real test
   split plain AraT5v2 wins (SARI 51.5–53.7 vs. 50.1–51.3), and its word-substitution step flipped negations and changed
   meaning. → Compare against **plain AraT5v2**; never use unchecked masked-LM substitution.
2. **Constrain the generator lexically** — unconstrained "write easy Arabic" prompting controls readability poorly (Rabih et al., 2026).
3. **LLM-judge-built training data works without a parallel corpus** (Wu et al., 2025) — but only if the judge actually rejects bad pairs.
   Test it on real negatives from **ArPC / APB** non-paraphrase pairs.
4. **LLMs may beat the fine-tuned student** (Qiang et al., 2025) — benchmark zero-shot LLMs honestly.
5. **Metrics are fragile:** copying the input scores SARI 39–46 on Baseet's data; SARI implementations differ by ~8 points.
   → Pin one scoring script, always report a copy baseline, add an error-based human evaluation.
6. **Build our test set like DAASI** (CC0): LLM drafts verified by two annotators, a third resolves disagreements.
7. **Check level control:** outputs must actually differ across levels and get easier; avoid single huge level jumps.
8. **UX:** let readers see the original or request synonyms instead of silently rewriting.

## 6. Evaluation protocol

Every system is scored on the same inputs with one pinned script, against a copy-the-input baseline. The two locked
test sets (BAREC test, 7,286 rows; SAMER test, 3,277 rows) live in `data/test_locked/`, which git ignores; only
`data/test_manifest.json` with their row counts and SHA-256 hashes is committed. Reference-based scores (SARI) are
reported on changed rows only; the task-specific evaluation is BayanBench (section 4a). How to score a trained model:
[`scripts/evaluation/README.md`](scripts/evaluation/README.md). Background:
[`references/02_text_simplification/evaluation_and_benchmarking.md`](references/02_text_simplification/evaluation_and_benchmarking.md).

## 7. Repository layout

```
Bayan/
├── README.md                      # This file
├── CONTRIBUTING.md                # Team workflow: branches, PRs, reviews
├── .github/                       # CODEOWNERS, PR and issue templates
├── app/                           # Android plugin (PROCESS_TEXT), Jetpack Compose + Material 3 Expressive
│   └── design-system/             # Bayan design system: logo, tokens, components, banners, reading guidelines
├── bayanbench/                    # BayanBench v2.0: the task benchmark (package, tests, README)
├── deliverables/                  # SIC capstone deliverables (action plan, WBS, report, slides, demo)
├── docs/                          # Model results, the diacritization comparison
│   ├── brand/                 # Rendered banners (README, social); source in app/design-system
│   └── decisions/                 # Decision records — what we chose, and why
├── references/                    # Literature review, benchmarks, and the project's reference architecture
│   ├── INDEX.md                   # Start here
│   ├── 00_project_brief/          # Original idea brief (historical)
│   ├── 01_problem_motivation/     # Verified dyslexia & reading evidence
│   ├── 02_text_simplification/    # Datasets, systems, evaluation, architecture decisions, Baseet analysis
│   └── 03_project_architecture/   # Pipeline architecture & execution plan (LaTeX)
├── scripts/                       # Data pipeline, classifiers, DSPy validator optimization
│   ├── compiled/                  # Compiled DSPy programs
│   ├── training/                  # model1_training.ipynb; model2/ (train.py, sari.py, both notebooks)
│   └── evaluation/                # Scoring, leakage check, test-set manifest (+ fixtures/)
├── data/                          # README + human annotations (raw/processed data are git-ignored)
│   └── test_manifest.json         # Hashes of the locked test sets; the sets themselves are never committed
├── pyproject.toml                 # Python dependencies (uv)
└── .env.example                   # API key template — copy to .env, never commit keys
```

## 8. Getting started

```bash
uv sync                                  # install dependencies (Python ≥ 3.12; includes torch)
cp .env.example .env                     # add your DEEPSEEK_API_KEY
# download BAREC — see data/README.md
uv run python scripts/camel_readability.py   # optional: fetch the CAMeL readability model now (else the first run does)
uv run python scripts/barec_simplification_pipeline.py --dry-run
```

The CAMeL readability model needs no manual setup: it runs on an NVIDIA GPU when there is one (`--device cpu|cuda|auto`),
otherwise on CPU through an ONNX export that is made once on first use (about a minute) and cached in `models/`.
`uv sync` installs torch with its CUDA libraries on Linux. On a machine without a GPU you can skip them by installing
outside the lockfile and running with `--no-sync` afterwards (a plain `uv run` re-syncs to the lockfile):

```bash
uv venv
UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu UV_INDEX_STRATEGY=unsafe-best-match uv pip install -r pyproject.toml
uv run --no-sync python scripts/camel_readability.py
```

Before any training file is used, check it for test-set leakage:

```bash
uv run python scripts/evaluation/check_leakage.py <training_file> \
    --reachable data/raw/barec/train.csv --reachable data/raw/barec/dev.csv
```

## 9. Team Cogni

| Member | Role | Responsibilities |
|---|---|---|
| Marwan Elamami | Team Leader & Application Lead | Project management; architecture and integration; application; read-aloud with highlighting |
| Abdulrahman Khengari | Data Lead | Simplification corpus; data quality control; annotation guidelines; BayanSimplify-v0.3; the pitch deck |
| Ahmed Alaeb | Model Training Lead | Training the simplification model(s) for on-device use; integrating the diacritization model |
| Sanad Ali | Machine Learning Engineer | Co-training the simplification model(s); diacritization benchmark; data annotation and quality review; presents the pitch |
| Mohammed Thabet | Application Engineer | Application; read-aloud with highlighting; data annotation and quality review |
| Abdul Majid Mraied | Evaluation & Benchmarking Lead | Test set design; benchmarking; automatic and human evaluation |

## 10. Contributing

Never push to `main` — every change goes through a reviewed pull request. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 11. Open items

- Bring the AraT5v2 bundles under 250 MB by pruning the vocabulary to the pieces Arabic text uses (about 223 MB).
- Faster beam decoding, so BayanSimplify-v0.3's quality also arrives word by word.
- A reading study with more readers with dyslexia, measuring reading time and comprehension.
