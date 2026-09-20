# Architecture Decisions for Arabic Text Simplification

Supports: Final Report 2.2 (Training Methodology), 2.4 (System Design), 3.3 (Modeling).
Separates what the literature supports from what is a design judgment. Verified 2026-09-17;
§1.1 (decoder-only evidence) and the model-size table added 2026-09-20.

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

| Model | Parameters | Vocab | Checkpoint |
|---|---|---|---|
| `UBC-NLP/AraT5v2-base-1024` | ~368M | 110,208 (untied output head) | 1.47 GB (`pytorch_model.bin`) |
| `moussaKam/AraBART` | ~139M | ~50K | — |
| `HPLT/hplt_t5_base_3_0_ara_Arab` | ~230M (estimated) | 32,768 | — |
| `flax-community/arabic-t5-small` | ~110M | — | 439 MB |

AraT5v2's two 110,208 × 768 embedding matrices account for **169M parameters — about 46% of the
model**. Vocabulary pruning to the tokens Arabic sentence data actually uses is therefore the largest
available size reduction that costs no quality, and it applies to whichever base is chosen. HPLT's
Arabic T5 reaches the same effect by design, with the same body capacity as AraT5v2.

### 1.1 Architecture and faithfulness: what the evidence actually supports

*Settled 2026-09-20 against four independent human evaluations. Read this before repeating the
"encoder-decoder is more faithful" argument anywhere in the report, slides or pitch.*

The original project brief rejected decoder-only Arabic SLMs for the *deployed* simplifier on the
grounds of "assistant drift" — added explanation, looser rephrasing, hallucination — with no source.

**The literature does not support that claim as stated, and one paper directly contradicts it.**
Wu & Arase (2025) ran an error-based *human* evaluation on sentence simplification — Bayan's exact
task — and found the fine-tuned encoder-decoder was the **worst** system tested:

| System | Params | Architecture | Total errors | Altered Meaning (lexical) |
|---|---|---|---|---|
| Qwen2.5-72B | 72B | decoder-only | 172 | 59 |
| GPT-4 | undisclosed, ≫10B | decoder-only | 211 | 94 |
| Llama-3.2-3B | 3B | decoder-only | 326 | — |
| **Control-T5** (fine-tuned seq2seq SOTA) | **220M** (T5-base) | **encoder-decoder** | **350** | **176** |

Control-T5 is the authors' own replication of Sheang et al.'s controllable simplifier: **T5-base
fine-tuned on WikiLarge**, with Optuna hyperparameter search (Wu & Arase §4, "Replicated
Control-T5"). That matters for Bayan in both directions. It is the *same architecture family and the
same order of magnitude* as AraT5v2-base (368M), so the comparison is like-for-like rather than a
strawman — but it also means the worst system in the study is the one Bayan's deployed model most
closely resembles.

Read the table by the params column and the ordering is exact: **error count rises monotonically as
size falls, across both architectures.** The two worst systems are the only two at deployable size.

So "an encoder-decoder preserves meaning better than an LLM" is **false** as a general statement, and
must not appear in Bayan's deliverables. The claim that the same evidence *does* support is narrower
and conditioned on **deployable size**:

> At the model sizes Bayan can actually ship, a fine-tuned encoder-decoder is the better bet.
> Larger LLMs are better still, but cannot run on-device — which is precisely why Bayan uses them
> offline as generators and judges rather than as the product.

A second independent human study agrees. In SALSA (19K edit annotations, 840 simplifications),
fine-tuned **MUSS** (BART-large) "produce[s] more diverse edits than GPT-3.5, yet suffer[s] from
**incredibly high errors**", while fine-tuned **T5-3B/11B** "learn to **minimize loss by making very
few changes**". Across all systems 16% of edits are errors and **63% of simplifications contain at
least one error**. So both failure modes Bayan must avoid — copying and meaning errors — are
documented *in fine-tuned encoder-decoders*.

| Evidence for the size-conditioned claim | Source |
|---|---|
| The only small decoder-only model tested (Llama-3.2-3B) produced roughly twice the errors of the 72B model, and **Repetition and Hallucination were notably more frequent** than in any other system | Wu & Arase, ACM, July 2025, [arXiv:2403.04963](https://arxiv.org/abs/2403.04963) · [doi:10.1145/3744744](https://doi.org/10.1145/3744744) |
| Open instruction-tuned models (Alpaca, Vicuna) matched GPT-3.5's edit count but with **more conceptual errors, "due to the inherent limits of model imitation"** | Heineman, Dou, Maddela & Xu, EMNLP 2023, [2023.emnlp-main.211](https://aclanthology.org/2023.emnlp-main.211/) |
| Small on-device LLMs' "**limited capacity** compared to larger counterparts introduces critical considerations regarding the **reliability and harmfulness**" of their simplifications | Hayakawa, Bott & Saggion, INLG 2025, [arXiv:2509.25086](https://arxiv.org/abs/2509.25086) |
| At **sub-1B** scale, fine-tuning beats prompting: human raters preferred fine-tuned outputs **46.9% vs 31.5%** (p = 0.0062), while prompting scored well on BERTScore largely by **copying the input** | Cohen, Bul, Inbar & Loewenbach, 2026, [arXiv:2601.05794](https://arxiv.org/abs/2601.05794) |
| Over-editing **survives fine-tuning**: on BEA-19, fine-tuned Chat-LLaMA-2-7B/13B reach precision 72.3 / 74.6, while a **770M** T5-large reaches 78.0 and the best F0.5 | Park, Do & Lee (2025), [arXiv:2509.20811](https://arxiv.org/abs/2509.20811) |
| **In Arabic:** 3–14B LLMs underperformed specialized models on Arabic GEC, the gap narrowing as scale grows | Dekmak (AUB thesis, 2026) |
| **In Arabic:** GPT-4 reaches F0.5 67 on QALB-2014 against 80.09 for fine-tuned AraT5 — though this compares a prompted LLM with a fine-tuned model, so it shows the value of in-domain fine-tuning, not of the architecture | Alrehili & Alhothali (2025), [arXiv:2511.14230](https://arxiv.org/abs/2511.14230) |
| ChatGPT **over-corrects and does not follow the minimal-edit principle**; GPT-3.5/GPT-4 score well on fluency-oriented benchmarks and poorly on minimal-edit ones | Fang et al. (2023), [arXiv:2304.01746](https://arxiv.org/abs/2304.01746); Coyne et al. (2023), [arXiv:2303.14342](https://arxiv.org/abs/2303.14342) |

| Caution — do not overclaim | Source |
|---|---|
| Fine-tuned encoder-decoders altered lexical meaning **more** than GPT-4 and Qwen2.5-72B, and overfit during fine-tuning (96 of Control-T5's 104 coreference errors came from one dataset) | Wu & Arase (2025) |
| Insertion, deletion and substitution errors occur in encoder-decoder simplifiers **and in the reference corpora themselves**, undetected by standard metrics | Devaraj, Sheffield, Wallace & Li, ACL 2022, [2022.acl-long.506](https://aclanthology.org/2022.acl-long.506/) |
| LLMs beat non-LLM methods across simplification tasks, sometimes exceeding human references | Qiang et al. (2025) |

**Reading:** architecture is not a faithfulness guarantee, and Bayan should never claim it is. Across
four independent human evaluations the pattern is consistent — **capacity, not architecture, predicts
meaning errors.** Every deployable-size system studied, of either architecture, produces them at
non-trivial rates (16% of edits, 63% of simplifications, in SALSA).

#### Objections to this reading, and what answers them

These are the three challenges the argument has actually received. Each is answered here so the
answer is on record before it is needed in a review.

**1. "AraT5v2 is a second-generation model pretrained on far more Arabic data than T5-base ever saw.
Doesn't that change the result?"**

The study contains its own test of this. **Llama-3.2-3B was pretrained on roughly 9T tokens** (Meta's
reported figure for the Llama 3.2 1B/3B corpus) against T5's **~34B** — about two orders of magnitude
more data, a modern recipe, and distillation from larger models. It still produced **326 errors, close
to double Qwen2.5-72B's 172**. Within this experiment, pretraining scale did not substitute for
capacity on *this specific failure mode*.

Wu & Arase also found Control-T5's errors were **concentrated rather than diffuse** — 96 of its 104
coreference errors came from a single dataset — which points at overfitting during *fine-tuning*, not
a pretraining deficiency. Pretraining scale does not fix that, and Bayan fine-tunes on a small set
(SAMER plus ~5.6k synthetic pairs), which is exactly the regime where it happens.

So AraT5v2's stronger pretraining is a reason to expect it to beat AraT5v1. It is not evidence that it
escapes the size effect.

**2. "All of this evidence is English."**

Correct, and it is a real limitation rather than a rhetorical one. No Arabic study measures
simplification errors at this granularity. The two Arabic rows in the evidence table above are
**grammatical error correction, not simplification**, and one of them compares a *prompted* LLM with a
*fine-tuned* model — so it speaks to the value of in-domain fine-tuning, not to architecture.

The honest position is therefore that the transfer to Arabic is **untested in both directions**. That
is a weak thing to say in a defence, which is the argument for measuring it ourselves (below).

**3. "Our equivalence judge catches meaning errors, so this is already handled."**

It catches some, at a different point in the pipeline from where these papers measured.
`optimize_equivalence_validator.py` compiles the judge against real human verdicts and production uses
a conservative 0.7 threshold — genuinely stronger than metric-only filtering, and a real answer to
Devaraj et al. But three gaps remain:

- It filters **training data**; it does not gate **model output**. Wu & Arase measured errors at
  inference. Control-T5 was trained on standard corpora and still made 350. Nothing currently checks
  meaning between Bayan's model and a reader — that is E2, still scoped as a stretch goal.
- **SAMER does not pass through the judge at all.** It is the human-authored corpus the first model
  trains on, and Devaraj's finding is precisely about errors inside such corpora.
- The judge's accuracy is measured **batch-of-1** while production scores **5 candidates per call**;
  its own module docstring records that the anti-anchoring instruction is "an instruction, not a
  guarantee."

#### What would actually settle this for Arabic

An error-based human annotation of Bayan's **own** outputs — roughly 50 simplifications marked by
error type, following Wu & Arase's taxonomy. That is a few hours of work and it yields:

- the first Arabic data point of this kind, as a genuine contribution for the final report;
- a direct reply to "your own citation says this architecture was worst" — *in English, at 220M, on
  WikiLarge; here is ours, in Arabic*;
- a faithfulness number that does not depend on transferring anyone else's result.

Until that exists, Bayan's faithfulness claim rests on the verification gate, not on the architecture
and not on the literature.

**The settled position for Bayan's deliverables:**

> Bayan deploys a fine-tuned sub-1B encoder-decoder because at deployable scale fine-tuning beats
> prompting (Cohen et al., 2026), and the large LLMs that outperform it cannot run on-device.
> No model class is faithful by construction, so faithfulness is **enforced by a verification gate,
> not inherited from the architecture**.

Two consequences that change the plan rather than just the wording:

1. **Distillation is a safety risk, not only a quality risk.** Hayakawa et al. (INLG 2025) found that
   knowledge distillation into a small model *raised automatic scores while increasing the proportion
   of **harmful** simplifications*, judged manually. Any Bayan distillation or compression step must
   therefore be evaluated by human meaning review, not by SARI alone — the metric will improve while
   the harm rate rises.
2. **The runtime faithfulness gate should be core, not a stretch goal.** It currently appears as
   stretch item E2 in `execution_plan.tex`. On this evidence it is the component the faithfulness
   claim actually rests on. Hayakawa et al. also give a cheap implementation: the model's own **output
   log-probability** is an effective detector of harmful simplifications, needing no second model.

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
