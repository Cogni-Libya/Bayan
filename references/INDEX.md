# Bayan (بيان) — References Index

**Core problem:** Arabic text simplification (ATS) for readers with dyslexia — reducing vocabulary,
syntactic and morphological complexity while preserving meaning.
**Auxiliary modules** (needed for a complete product, not the research focus): diacritization and
read-aloud with word highlighting. They get short verified pointers below, not full dossiers.

All content was checked against primary sources (papers, DOIs, arXiv, Hugging Face / GitHub registries,
and the local BAREC data) on **2026-09-17**. Unverifiable claims were removed. Before citing anything in
the SIC report or slides, cite the **primary source** listed, not these notes.

---

## Directory

```
references/
├── INDEX.md                                        # This file
├── 00_project_brief/
│   └── original_project_brief.md                   # The original idea brief (historical; superseded by
│                                                   # the root README.md)
├── 01_problem_motivation/
│   └── arabic_reading_and_dyslexia_evidence.md     # Verified prevalence & reading statistics; evidence
│                                                   # relevant to simplification; list of removed claims
└── 02_text_simplification/
    ├── arabic_simplification_literature.md         # Datasets (SAMER, ATSC, BAREC…), published systems,
    │                                               # related work, corrections to earlier notes
    ├── evaluation_and_benchmarking.md              # Metrics (SARI, BLEU, BERTScore), metric-reliability
    │                                               # evidence, readability (BAREC levels, AARI, OSMAN),
    │                                               # benchmark protocol for Bayan
    ├── architecture_decisions.md                   # Why fine-tuned AraT5v2; generate-and-rerank data
    │                                               # pipeline; internal results; design changes
    └── baseet_baseline_analysis.md                 # Our re-analysis of Baseet's published predictions
└── 03_project_architecture/                        # The project's reference architecture (team documents)
    ├── pipeline_architecture.tex                   # Three-stage pipeline design, QC pipeline, SWOT, risks
    └── execution_plan.tex                          # Milestones, dependency flow, task groups A–F
```

| File | Use it for | SIC Final Report section |
|---|---|---|
| `01_problem_motivation/arabic_reading_and_dyslexia_evidence.md` | Problem statement, pitch statistics, dyslexia-specific simplification evidence | 1.1, 1.2 |
| `02_text_simplification/arabic_simplification_literature.md` | Data sources, prior systems, related work | 2.1, 2.2, 3.3 |
| `02_text_simplification/evaluation_and_benchmarking.md` | Evaluation design and result reporting | 3.5 |
| `02_text_simplification/architecture_decisions.md` | Model and pipeline justification | 2.2, 2.4, 3.3 |
| `02_text_simplification/baseet_baseline_analysis.md` | Choosing and reporting the Baseet baseline | 3.3, 3.5 |
| `03_project_architecture/pipeline_architecture.tex` | System design and data/QC pipeline | 2.2, 2.4, 3.3 |
| `03_project_architecture/execution_plan.tex` | Planning and project management | Project Management (WBS) |
| `00_project_brief/original_project_brief.md` | History of the idea only — do not cite | — |

**Note on `03_project_architecture/`:** these LaTeX documents were written by the team before the
2026-09-17 audit. Where they conflict with the notes above, the notes win. Known updates: SAMER is used
for **evaluation only** (not training); diacritization and TTS use **ready pretrained models** (fine-tuning
only if time permits); the chosen TTS model is **Nabra-7M-Distill** (not Nabra-82M); the equivalence
validator currently rejects nothing and must be fixed before full-scale generation.

---

## Key insights from the 2026-09-17 research round

1. **Baseet's "best" hybrid model is not better, and it breaks meaning.** Its headline SARI was computed on
   all rows including training data. On its real test split, plain AraT5v2 beats the hybrid at every level
   (51.5–53.7 vs. 50.1–51.3), and the hybrid's word substitutions changed meaning in 11 of 12 sampled
   cases, including negation flips. → Use plain AraT5v2 as the baseline; never use unchecked masked-LM
   substitution. (`baseet_baseline_analysis.md`)
2. **For dyslexic readers, frequent and short words matter, and on-demand synonyms beat silent
   replacement** (Rello et al., 2013, Spanish user studies). → Optimize word frequency/length; let users see
   the original. (`01_problem_motivation`)
3. **Unconstrained LLM prompting controls Arabic readability poorly; lexical constraints fix it**
   (Rabih et al., LREC 2026). → Constrain Bayan's generator with lexicon levels. (`arabic_simplification_literature.md`)
4. **Parallel corpora are not required:** LLM-as-a-judge–built training data trained small models that beat
   GPT-4o on lexical simplification (Wu et al., 2025); AraT5v2 on distilled synthetic data beat 3–14B LLMs in
   Arabic grammar correction (Dekmak, 2026). → Supports Bayan's pipeline — if the judge works.
5. **But LLMs may still beat the fine-tuned student**, and often beat human references (Qiang et al., 2025).
   → Benchmark zero-shot LLMs honestly.
6. **Metrics are fragile:** copying the input scores SARI 39–46 on Baseet's data; SARI implementations
   differ by ~8 points; readability formulas correlate poorly with human judgments (Cardon & Doğruöz, 2026).
   → Pin the implementation, report a copy baseline, add error-based human evaluation.
7. **Datasets are not what they seem:** DAASI (CC0) is GPT-4o drafts verified by two annotators — a model
   for Bayan's test set; ATSC is on GitHub; the EW-SEW repo holds only a fraction of the paper's pairs;
   Al-Safy publishes no data; MultiSim and mEdIT have no Arabic simplification data. ArPC/APB non-paraphrase
   pairs can test the equivalence judge.
8. **Auxiliary features are already on the market** (e.g. an iOS diacritize + read-aloud app, 2026) without
   simplification or a dyslexia focus. → Bayan's differentiator is simplification.

---

## Key insights from the 27–30 Sep evaluation round

1. **SARI on SAMER rewards doing nothing.** Copying scores 77.5 on SAMER test; model 1 beats copying on the
   rows a human changed and still loses overall. Report the copy baseline and the changed/unchanged split.
2. **A public corpus was contaminated:** 9.3% of Baseet's rows overlap the SAMER and BAREC test sets.
   Run the leakage check on every training file.
3. **BayanBench** scores what a reader needs, track by track: model 2 makes text easier (long clauses fixed
   in 51–55% of items, hard words reduced in 41–44%) and keeps most content, but lacks restraint (easy text
   left unchanged in 9–11%) and rewrites protected text. See
   [`02_text_simplification/evaluation_and_benchmarking.md`](02_text_simplification/evaluation_and_benchmarking.md) §5.
4. **The deployed format matters:** the app's bundles send no strength tag and simplify less than the tagged
   model; int8 pushes AraT5v2 toward copying and barely moves AraBART.
5. **The phone is fast enough:** on a Snapdragon 870 the first token appears in 177–318 ms, and later
   sentences start within 85 ms, because output streams.

## Key verified facts

| Topic | Fact | Source |
|---|---|---|
| Dyslexia prevalence | 11% pooled across Arab countries (18 studies, N = 30,243); Gulf 24%, non-Gulf 13% | Aldakhil (2024), doi:10.1016/j.ridd.2024.104812 |
| Only human multi-level Arabic simplification corpus | SAMER: 15 novels, Levels 5 → 4 → 3, 20,603 fragments; no published model baselines | Alhafni et al. (2024), arXiv:2404.18615 |
| Main readability corpus | BAREC: 69,441 sentences, 19 levels, QWK 81.8%, CC BY-SA 4.0, not parallel | Elmadani et al. (2025), arXiv:2502.13520 |
| Published ATS results | ATSimST SARI 0.81 and TSimAr 0.73 (ATSC, 0–1 scale); Al-Thanyyan & Azmi SARI 37.15 (WikiLarge, 0–100) — **not comparable** | See `evaluation_and_benchmarking.md` |
| Data-pipeline precedent | Generate candidates with LLMs, filter by readability, rank by semantic similarity — won TSAR 2025 | EhiMeNLP (2025), doi:10.18653/v1/2025.tsar-1.18 |
| Readability classification ceiling | BAREC Shared Task 2025 winner !MSA: 87.5 QWK (sentence) | arXiv:2509.10040 |
| AARI formula | AARI Base = 3.28 × NoC + 1.43 × AWL + 1.24 × ASL (the handoff's formula is not AARI) | Al-Tamimi et al. (2014), IAJIT 11(4) |

---

## Auxiliary modules — verified pointers only

| Module | Verified facts | Source |
|---|---|---|
| Diacritization (Stage 2) | **CATT**: character-based encoder-only and encoder-decoder models; relative DER improvements of 30.83% (WikiNews) and 35.21% (CATT set); 9.36% relative DER better than GPT-4-turbo on the CATT set. Repo `abjadai/catt` is Apache-2.0; package `catt-tashkeel` installs. | arXiv:2407.03236 |
| Diacritics and reading | Full diacritics incurred only a **small** processing cost (visual crowding) in an eye-tracking study of homographic verbs; diacritics were mostly not processed when superfluous | Hermena et al. (2015), JEP:HPP 41(2), 494–507, doi:10.1037/xhp0000032 |
| TTS (Stage 3) | **Nabra-82M** (StyleTTS2/Kokoro): ONNX fp16 163.4 MB, int8 83.2 MB, int4 56.9 MB (`marwanelamami/nabra-82m-sherpa-onnx`, Apache-2.0); conversion scripts merged into sherpa-onnx (PR #3898). **MMS-TTS-Ara** (`facebook/mms-tts-ara`): 36.3M parameters, **CC-BY-NC-4.0**. | Hugging Face / GitHub registries |
| Word timing | torchaudio's **MMS_FA** forced aligner expects **romanized** text (e.g. via uroman) — Arabic script cannot be passed directly; trained on 23,000 hours in 1,100+ languages | torchaudio forced-alignment tutorial |
| Typography | **Maqroo**, an open-source Arabic dyslexia-friendly font by Omantel with Leo Burnett Dubai, launched February 2025. **Arabolexia** was studied with 45 dyslexic children, comparing letterform, spacing and font size against Simplified Arabic. | Omantel announcement; Benmarrakchi et al. (2024), IJAES 25(2), doi:10.33806/ijaes.v25i2.827 |

---

## Cleanup record (2026-09-17)

Removed, because they were out of scope, duplicated, or contained fabricated or incorrect content:

| Removed | Reason |
|---|---|
| `01_problem_and_epidemiology/empirical_source_verification_audit.md` | AI-generated "audit" that introduced a non-existent DOI and kept wrong ones |
| `02_cognitive_and_linguistic_foundations/arabic_orthography_and_dyslexia_science.md` | Mostly diacritics/visual-processing science (auxiliary); unsourced eye-tracking table; verified, relevant parts moved into `01_problem_motivation` |
| `03_text_simplification_and_architectures/architectural_comparative_analysis.md` and its copy `report/literature_review_and_benchmarks.md` | Benchmark table with invented scores and Bayan targets presented as results; rewritten as `architecture_decisions.md` |
| `03_text_simplification_and_architectures/public_benchmarks_and_readability_models.md`, `arabic_text_simplification_literature.md` | Contradictory dataset facts (SAMER, ATSC, BAREC winner) and unsourced numbers; verified content merged into `02_text_simplification/` |
| `04_systems_and_assistive_engineering/on_device_ai_and_multisensory_ui.md` | TTS / UI / on-device blueprint (auxiliary) with wrong model sizes, a pipeline without simplification, and non-working alignment code; verified facts kept above |

A backup of the original files is at `~/MyProjects/Bayan_references_original_2026-09-17.tar.gz`
(outside the repository).

---

## Required citation

Any report or publication using SAMER must cite:

```bibtex
@inproceedings{alhafni-etal-2024-samer,
    title = "The {SAMER} {A}rabic Text Simplification Corpus",
    author = "Alhafni, Bashar and Hazim, Reem and Pi{\~n}eros Liberato, Juan Diego and Al Khalil, Muhamed and Habash, Nizar",
    booktitle = "Proceedings of the 2024 Joint International Conference on Computational Linguistics, Language Resources and Evaluation (LREC-COLING 2024)",
    year = "2024",
    address = "Torino, Italia",
    publisher = "ELRA and ICCL",
    pages = "16079--16093"
}
```

Pages verified against the ACL Anthology record (2024.lrec-main.1398); the handoff's "789--801" is wrong.
