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
| **1. Simplify (core)** | Shorten and restructure sentences, replace rare words, keep meaning | **Primary focus.** Fine-tune one or more pretrained Arabic encoder-decoder (seq2seq) Transformers; AraT5v2 is the current candidate |
| 2. Diacritize | Restore full tashkeel on the simplified text | **Secondary.** Use a ready pretrained model (e.g. CATT); fine-tune only if time permits. Must never alter base letters |
| 3. Read aloud | TTS with word-by-word highlighting | **Secondary.** Ready model: **Nabra-7M-Distill** |

Order matters: simplify → diacritize → read aloud, because diacritics depend on the final wording.
An optional runtime quality gate shows the original text when a simplification is judged unfaithful.

## 3. Data — we build our own simplification corpus

No large, open, parallel Arabic simplification corpus exists, so Bayan builds one:

- **Source sentences:** [BAREC](https://huggingface.co/datasets/CAMeL-Lab/BAREC-Shared-Task-2025-sent)
  (CAMeL Lab, 69,441 sentences, 19 readability levels, CC BY-SA 4.0, **not parallel**). See [`data/README.md`](data/README.md).
- **Generate-and-rerank pipeline** ([`scripts/barec_simplification_pipeline.py`](scripts/barec_simplification_pipeline.py)):
  easy sentences and scripture are kept verbatim; each hard sentence gets several LLM-generated candidates, scored by an
  LLM equivalence judge (DSPy) and a fine-tuned MARBERT readability classifier; the best passing candidate is kept and
  annotators review samples. A **2% pilot run is complete**.
- **SAMER** is **not** used for training. The team has CAMeL Lab's approval to use its test split **for evaluation only**;
  SAMER data must never be committed or redistributed.
- **Diacritization check data:** Tashkeela.

## 4. Where we stand (internal results, not peer-reviewed)

| Component | Result | Implication |
|---|---|---|
| Readability classifier (easy/hard, 800-sentence held-out set) | MARBERT 86.8–87.5% (best); ensemble 84.8% | Usable as a filter; use an independent CAMeL BAREC model as the *evaluation* judge |
| Equivalence validator (DSPy MIPROv2, 25 held-out pairs) | Rejected **nothing** (0 true negatives) | **Must be fixed before full-scale generation** |
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
- **Test sets:** team-verified BAREC test set · SAMER test split (evaluation only) · DAASI / ATSC as out-of-domain.
- **Metrics:** SARI (pinned, fixed Arabic normalization) · BLEU (secondary) · readability drop (independent CAMeL BAREC model) ·
  meaning preservation (judge independent of the generator) · level-control checks · error-based human evaluation · DER/WER for stage 2.
- **Leakage:** never score on rows a model trained on.

Details: [`references/02_text_simplification/evaluation_and_benchmarking.md`](references/02_text_simplification/evaluation_and_benchmarking.md).

## 7. Repository layout

```
Bayan/
├── README.md                      # This file
├── CONTRIBUTING.md                # Team workflow: branches, PRs, reviews
├── .github/                       # CODEOWNERS, PR and issue templates
├── deliverables/                  # SIC capstone deliverables (action plan, WBS, report, slides, demo)
├── references/                    # Literature review, benchmarks, and the project's reference architecture
│   ├── INDEX.md                   # Start here
│   ├── 00_project_brief/          # Original idea brief (historical)
│   ├── 01_problem_motivation/     # Verified dyslexia & reading evidence
│   ├── 02_text_simplification/    # Datasets, systems, evaluation, architecture decisions, Baseet analysis
│   └── 03_project_architecture/   # Pipeline architecture & execution plan (LaTeX)
├── scripts/                       # Data pipeline, classifiers, DSPy validator optimization
│   └── compiled/                  # Compiled DSPy programs
├── data/                          # README + human annotations (raw/processed data are git-ignored)
├── pyproject.toml                 # Python dependencies (uv)
└── .env.example                   # API key template — copy to .env, never commit keys
```

## 8. Getting started

```bash
uv sync                                  # install dependencies (Python ≥ 3.12)
cp .env.example .env                     # add your DEEPSEEK_API_KEY
# download BAREC — see data/README.md
uv run python scripts/barec_simplification_pipeline.py --dry-run
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

- Fix and validate the equivalence judge on real negatives before generating the full corpus.
- Add lexical constraints and few-shot examples to the generator.
- Build and annotate the team-verified test set.
- Reproduce the plain AraT5v2 baseline on our test sets.
- Find dyslexic readers / schools for user testing.
- The schedule in the Action Plan is a working draft and may change.
