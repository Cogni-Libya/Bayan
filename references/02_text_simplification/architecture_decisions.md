# Architecture Decisions for Arabic Text Simplification

Supports: Final Report 2.2 (Training Methodology), 2.4 (System Design), 3.3 (Modeling).
Separates what the literature supports from what is a design judgment. Verified 2026-09-17.

---

## 1. Simplification model: fine-tuned encoder-decoder (AraT5v2)

**Decision:** fine-tune `UBC-NLP/AraT5v2-base-1024` as the deployed simplifier; use large LLMs only
offline, to generate training data.

| Supporting evidence | Source |
|---|---|
| Fine-tuned AraT5v2 is an established base for Arabic-to-Arabic rewriting (dialect → MSA) | AraT5-MSAizer, Fares (2024) |
| Seq2seq models trained on parallel data are the main published Arabic simplification systems (TSimAr, ATSimST, Al-Thanyyan & Azmi, Khallaf et al.) | See `arabic_simplification_literature.md` |
| A smaller model is feasible to quantize and run on-device; decoder-only LLMs at 7B+ parameters are much heavier | Model sizes (below) |
| For Arabic grammatical error correction, AraT5v2 trained on ~650K LLM-distilled synthetic pairs reached 80.86 F0.5 on QALB, and 3–14B LLMs underperformed specialized models | Dekmak (AUB thesis, 2026) |
| On Baseet's held-out split, fine-tuned AraT5v2 scores SARI 51.5–53.7 vs. 39.2–45.6 for copying the input | `baseet_baseline_analysis.md` |

| Caution | Source |
|---|---|
| Seq2seq models are **not** hallucination-free: Khallaf et al.'s mT5 produced divergent rewrites, and only 31 of 299 test sentences were correctly simplified overall | Khallaf, Sharoff & Soliman (2022) |
| LLMs outperformed non-LLM methods on all four simplification tasks studied, often beyond the human references — the LLM "teacher" may beat the AraT5 "student" | Qiang et al. (2025) |
| Level-token control can fail silently: 11.4% of Baseet's AraT5v2 test outputs are identical across all three levels; controllability depends on the training-data distribution | Baseet re-analysis; Hubarava & Gao (2026) |
| No published comparison exists between fine-tuned AraT5 and prompted Arabic LLMs on the same simplification test set | This audit |

"More faithful than an LLM" is therefore a **hypothesis to test** in Bayan's benchmark, not an
established result.

**Model sizes (checked on the Hugging Face Hub / measured locally):**

| Model | Parameters | Checkpoint |
|---|---|---|
| `UBC-NLP/AraT5v2-base-1024` | ~368M | 1.47 GB (`pytorch_model.bin`) |
| `flax-community/arabic-t5-small` | ~110M | 439 MB |

## 2. Training data: generate-and-rerank over BAREC

**Decision (current Bayan pipeline, `scripts/barec_simplification_pipeline.py`):**
BAREC is not parallel, so hard sentences (5-level 3–4) are rewritten by an LLM into several candidates,
which are filtered by a semantic-equivalence judge and a readability classifier; easy sentences and
scripture are kept unchanged.

| Supporting evidence | Source |
|---|---|
| Generate candidates with LLMs, then filter by readability and rank by semantic similarity, won the TSAR 2025 readability-controlled simplification task | EhiMeNLP (2025) |
| Building simplification training data with an LLM-as-a-judge, without any parallel corpus, produced small models that beat GPT-4o on lexical simplification | Wu, Arase & Nagata (2025) |
| BAREC provides 69,441 real sentences with 19-level labels under CC BY-SA 4.0 | Elmadani, Habash & Taha-Thomure (2025) |

| Risk | Source |
|---|---|
| All generated targets are LLM-written; no human reference exists unless the team adds one | Bayan pipeline design |
| The same LLM (DeepSeek) generates and judges equivalence, so their blind spots are correlated | `../03_project_architecture/pipeline_architecture.tex` |
| The "easy" band covers BAREC 19-levels 1–11, which is broad | BAREC level mapping (see `evaluation_and_benchmarking.md`) |

## 3. Bayan internal results (from `../03_project_architecture/pipeline_architecture.tex`, not peer-reviewed)

| Component | Result |
|---|---|
| Readability classifier (800-sentence balanced held-out set, easy/hard band accuracy) | MARBERT 86.8–87.5%; CAMeLBERT-mix 83.5–83.9%; binary head 83.4%; CORAL head 80.1%; 3-model majority vote 84.8%. The prior DSPy-prompted classifier reached 79.7%. |
| Semantic-equivalence validator (DSPy MIPROv2, 102 human-annotated pairs, 77 train / 25 held-out) | With the current batched signature, **every** held-out pair scored as equivalent (0 true negatives): the gate does not yet reject meaning changes. |
| BERTScore as an equivalence signal | r = −0.014 with human labels on the same annotations (one annotator). |

These are the team's own measurements. Report them as such, and fix the equivalence validator before
generating data at full scale.

## 4. Design changes suggested by the 2026-09-17 research round

| Change | Evidence |
|---|---|
| **Constrain the generator lexically** (e.g. allowed SAMER-lexicon levels or explicit word lists), instead of only asking for "easy" Arabic | Unconstrained prompting gave weak Arabic readability control; lexical constraints gave 0.99 agreement (Rabih et al., 2026) |
| **Add Arabic few-shot examples and an LLM revision pass** to candidate generation | Best synthetic-data strategy across 11 languages (Anikina et al., 2025) |
| **Choose the simplification policy explicitly** — for dyslexic readers, prioritize frequent and shorter words and avoid needless full rewrites | Policy-driven data (Wu et al., 2025); dyslexia evidence (Rello et al., 2013 — see `../01_problem_motivation/`) |
| **Never apply unchecked masked-LM word substitution**; protect negations and named entities | Baseet's lexical step flipped negations and swapped entities (`baseet_baseline_analysis.md`) |
| **Avoid single huge level jumps**; consider stepwise targets | LLMs struggle across large readability gaps (Zhang et al., 2026) |
| **Validate level tokens** by checking that outputs differ across levels and readability actually drops | Hubarava & Gao (2026); Baseet re-analysis |
| **Fix and test the equivalence judge on real negatives** (ArPC / APB non-paraphrases) before scaling generation | Bayan's validator currently rejects nothing |
| In the app, **let readers see the original or request simpler synonyms** rather than silently replacing text | Rello et al. (2013, W4A): on-demand synonyms beat automatic substitution for dyslexic readers |

## 5. Pipeline order (auxiliary stages)

Simplify first, then diacritize, then read aloud. Diacritics depend on the final wording and syntax, so
diacritizing before simplification would leave marks that no longer match. Diacritization and TTS are
supporting modules; verified pointers for them are in `../INDEX.md`.
