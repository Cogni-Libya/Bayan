# Bayan (بيان) — An AI Reading Assistant for Arabic Readers with Dyslexia

**Team Cogni** · Samsung Innovation Campus (SIC) AI Course — Capstone Project

Bayan simplifies complex Arabic text for readers with dyslexia while preserving its meaning, then adds
diacritics and reads it aloud with synchronized word highlighting.

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

| Stage | What it does | Status of the decision |
|---|---|---|
| **1. Simplify (core)** | Shorten and restructure sentences, replace rare words, keep meaning | **Primary focus.** Fine-tuned Arabic encoder-decoder (seq2seq) Transformers: model 1 (AraT5v2 on SAMER) and model 2 (AraT5v2 and AraBART, one model per architecture with a strength tag). Both model-2 models run in the app as int8 ONNX bundles |
| 2. Diacritize | Restore full tashkeel on the simplified text | **Secondary.** Selected: **Libtashkeel** (`text2tashkeel`): MIT, 4.8 MB, exports to ONNX, changed no base letters in the benchmark. Not in the current app build |
| 3. Read aloud | TTS with word-by-word highlighting | **Secondary.** In the app: **Nabra-7M-Distill** (int8, 8.7 MB) through sherpa-onnx, the spoken word highlighted; three Piper voices as optional downloads |

Order matters: simplify → diacritize → read aloud, because diacritics depend on the final wording.
An optional runtime quality gate shows the original text when a simplification is judged unfaithful.

### How it reaches the reader

Bayan ships as an **Android plugin**, not a separate app. It registers a `PROCESS_TEXT` intent, so "تبسيط"
appears in the text-selection menu of any app on the phone: the reader selects hard Arabic text where they
meet it, and a panel over the same app streams the simplified version sentence by sentence and can read it
aloud. The panel can float over the page or shrink to a bar while reading continues. The app is built with
Jetpack Compose and Material 3 Expressive and follows the system's dynamic colours rather than a design of its own. **All inference runs on the
device** — no server, no network, and the text never leaves the phone.

That constrains every model choice: ONNX Runtime Mobile only, nothing that needs Python at runtime or a GPU,
and a total download budget of roughly 250 MB. Full reasoning in
[`docs/decisions/0001-product-form.md`](docs/decisions/0001-product-form.md).

## 3. Data — we build our own simplification corpus

No large, open, parallel Arabic simplification corpus exists, so Bayan builds one:

- **Source sentences:** [BAREC](https://huggingface.co/datasets/CAMeL-Lab/BAREC-Shared-Task-2025-sent)
  (CAMeL Lab, 69,441 sentences, 19 readability levels, CC BY-SA 4.0, **not parallel**). See [`data/README.md`](data/README.md).
- **Generate-and-rerank pipeline** ([`scripts/barec_simplification_pipeline.py`](scripts/barec_simplification_pipeline.py)):
  easy sentences and scripture are kept verbatim; each hard sentence gets several LLM-generated candidates, scored by an
  LLM equivalence judge (DSPy) and the CAMeL BAREC readability model (`CAMeL-Lab/readability-arabertv02-word-CE`; it replaced
  the fine-tuned MARBERT classifier in #17); the best passing candidate is kept and
  annotators review samples. The current export holds **41,256 rows**, of which 5,585 are model-generated pairs and
  1,509 are human-written gold pairs from DAASI; the rest are identity pairs, scripture and poetry kept verbatim.
- **SAMER** *is* used for training. CAMeL Lab approved fine-tuning on it and publishing the resulting weights for
  non-commercial use. What is **not** allowed is redistributing the corpus, so SAMER text must never be committed,
  pasted into an issue, or included in any deliverable. Its official train split is the basis of our first model;
  its official test split is one of the two locked test sets.
- **Model 2 training data** (private Kaggle dataset `marwanelamami13/bayan-model2-data`, 22,733 pairs): SAMER L5→L3
  (14,343), DAASI train (1,502) and Baseet (6,888, filtered for meaning). Every source starts with a strength tag —
  `[S0]` minimal, `[S1]`–`[S3]` light to strong, `[SA]` everyday/administrative style — so one model covers every
  strength. The tag is part of the input only and is never shown. **Known gap:** the int8 bundles in the
  current app send the bare prefix without a tag, and BayanBench shows this weakens simplification (long
  clauses are fixed in 43.9% of items by the shipped AraBART bundle and in 55.1% by the same model with `[S2]`); the fix is to send `[S2]`.
- **Diacritization check data:** Tashkeela.
- **Leakage:** both training sets were checked against both locked test sets on 2026-09-21 and are clean. See
  [`scripts/evaluation/README.md`](scripts/evaluation/README.md).

## 4. Where we stand (internal results, not peer-reviewed)

| Component | Result | Implication |
|---|---|---|
| Readability classifier (easy/hard, 800-sentence held-out set) | MARBERT 86.8–87.5% (best of those tried); ensemble 84.8% | MARBERT was **replaced by CAMeL AraBERT** (#17): on SAMER it ranks the human-simplified version higher 80.1% of the time (sentence pairs) and 76.9% (word swaps), against about 76% and 72–74% for MARBERT. CAMeL now gates the data, so evaluate with a different model or with human review |
| Equivalence validator (DSPy MIPROv2, 25 held-out pairs) | 84% accuracy at threshold 0.70, up from 64% at the original guess of 0.8 | Directional only: 25 pairs is small; revisit with more annotations |
| Model 1: AraT5v2 on SAMER (dev, 2,983 rows) | SARI 77.06 vs 74.25 for copying; on the 1,754 rows people changed, 63.66 vs 56.21 (+7.46) | Beats copying, but makes conservative one-word edits and at least one meaning error; see [`docs/model1_samer_dev.md`](docs/model1_samer_dev.md) |
| Model 2: AraT5v2 vs AraBART (`select_dev`, 600 changed SAMER rows) | SARI 66.58 vs 64.71; AraBART generates 3.6× faster than AraT5v2 (292.8 vs 80.8 sentences/s on a T4, measured against model 1, same architecture) | Selection score only; the test evaluation is BayanBench (next row). See [`scripts/training/model2/README.md`](scripts/training/model2/README.md) |
| Model 2 on BayanBench test (1,250 items, code tier, `[S2]`), AraT5v2 / AraBART | Long-clause items with no clause over 15 words: 50.8% / 55.1% (copying: 0%). Fewer hard words: 41.2% / 44.0%. At least 60% of source words kept: 88.2% / 81.7%. Easy text left unchanged: 9.4% / 11.4%. Numbers kept: 76.3% / 74.0%; negations kept: 79.3% / 80.6% | Easier and mostly faithful, but no restraint: it edits easy text, rewrites protected scripture (letters kept in 4.4%) and completes cut-off selections. Full tables and intervals in the final report |
| On the device (int8 ONNX) | AraBART 222 MB, AraT5v2 471 MB. Laptop CPU per sentence (median / p90): 0.10 / 0.24 s vs 0.20 / 0.43 s. Xiaomi Mi 11X (Snapdragon 870), AraT5v2: cold load 2.6–7.3 s, first token 177–318 ms (first sentence) and 55–85 ms (later ones) | AraBART fits the 250 MB budget; quantisation moves it by less than 2 points on every code measure, while it pushes AraT5v2 toward copying |
| BERTScore as equivalence signal | r = −0.014 with human labels | Don't rely on it |

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

## 6. Evaluation plan

Same test inputs and one scoring script for every system:

- **Systems:** copy-the-input baseline · plain fine-tuned AraT5v2 (Baseet setup) · zero-shot LLMs (incl. lexically constrained) · Bayan.
- **Test sets:** two locked splits, both upstream and unmodified — the BAREC test split (7,286 rows) and the SAMER
  test split (3,277 rows). They live in `data/test_locked/`, which git ignores; only `data/test_manifest.json` with
  their row counts and SHA-256 hashes is committed, so everyone can prove they scored the same data.
  Model 2 is also scored on DAASI's held-out set (350 rows) and Baseet's test split (3,430 rows, with Baseet's own scorer).
  BAREC has no reference simplifications, so it carries the reference-free metrics and doubles as the
  out-of-domain check — SAMER splits by chapter, not by novel, so its test set is fully in-domain.
- **Metrics:** SARI (pinned, fixed Arabic normalization) · BLEU (secondary) · readability drop (independent CAMeL BAREC model) ·
  meaning preservation (judge independent of the generator) · level-control checks · error-based human evaluation · DER/WER for stage 2.
- **Leakage:** never score on rows a model trained on.

How to score a trained model: [`scripts/evaluation/README.md`](scripts/evaluation/README.md) ("Scoring a trained model");
the protocol for the report's tables is issue #30.

**BayanBench** is the task-specific benchmark: 1,981 items (dev 731 / test 1,250, split by document) in four
sets (core BAREC test, held-out news and legal, outside text published after every corpus, written medicine
sentences) and tracks for meaning, ease, restraint, correct Arabic, real selections, protected text and the
phone. A deterministic **code tier** runs anywhere; a **judge tier** (Gemini 3.1 Pro, fixed checklist) stores
verdicts as shared data, so nobody waits on a judge. Every rate has a 95% interval from a bootstrap over whole
documents, and the test split is run once per final model. The package (`verify`, `predict`, `score`,
`pending`, `judge`, `validate-judge`) is on branch `feat/bayanbench`; its data is the private HF dataset
`Congi-libya/bayanbench-data`. Background:
[`references/02_text_simplification/evaluation_and_benchmarking.md`](references/02_text_simplification/evaluation_and_benchmarking.md).

## 7. Repository layout

```
Bayan/
├── README.md                      # This file
├── CONTRIBUTING.md                # Team workflow: branches, PRs, reviews
├── .github/                       # CODEOWNERS, PR and issue templates
├── app/                           # Android app (Compose, Material 3 Expressive, PROCESS_TEXT, on-device ONNX); licences in app/licenses/
├── deliverables/                  # SIC capstone deliverables (action plan, WBS, report, slides, demo)
├── docs/                          # Model results, the diacritization comparison
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
| Abdulrahman Khengari | Data Lead | Simplification corpus; data quality control; annotation guidelines |
| Ahmed Alaeb | Model Training Lead | Training the simplification model(s) for on-device use; integrating the diacritization model |
| Sanad Ali | Machine Learning Engineer | Co-training the simplification model(s); data annotation and quality review |
| Mohammed Thabet | Application Engineer | Application; read-aloud with highlighting; data annotation and quality review |
| Abdul Majid | Evaluation & Benchmarking Lead | Test set design; benchmarking; automatic and human evaluation |

## 10. Contributing

Never push to `main` — every change goes through a reviewed pull request. See [`CONTRIBUTING.md`](CONTRIBUTING.md).

## 11. Open items

- Send the strength tag (`[S2]`) from the app's bundles.
- Keep scripture and poetry away from the model (return them unchanged, with their tashkeel), keep a
  cut-off selection's ending, and map Persian-range digits before decoding.
- Fill BayanBench's judge tier for the final models, and run its blind human rating (100 items).
- Validate the equivalence judge on more annotated pairs, including real negatives.
- Signed release build (#31 Part 2).
- Name who presents at the final pitch and who writes the slides.
- Find dyslexic readers / schools for user testing.
