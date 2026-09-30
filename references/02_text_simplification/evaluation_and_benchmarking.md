# Evaluating Arabic Text Simplification: Metrics, Readability, and Benchmarking

Supports: Final Report 3.5 (Testing and Improvements) and the Result score (30/100).
Verified 2026-09-17. Items marked *recommendation* are our proposals, not findings from a paper.

---

## 1. The published numbers are not comparable

| System | Test data | Score | Scale |
|---|---|---|---|
| ATSimST (2025) | ATSC, random 30% test split of 500 documents | SARI 0.81, BLEU 0.69 | 0–1 |
| TSimAr (2023) | ATSC | SARI 0.73, BLEU 0.65 | 0–1 |
| Al-Thanyyan & Azmi (2023), hybrid | Translated WikiLarge, 249 sentences | SARI 37.15, BLEU 55.68 | 0–100 |
| Khallaf et al. (2022) | Saaq al-Bambuu, 299 test sentences | BERTScore F1 0.97 / 0.70 only | 0–1 |
| Any model | SAMER test split | **none published** | — |

Different datasets, splits, tokenization and scales mean these cannot be ranked against each other,
and there is no public Arabic simplification leaderboard. A claim that Bayan "beats" a published model
is only valid when both are run on the **same test set with the same scoring code**.

## 2. Metrics

### SARI
Xu, Napoles, Pavlick, Chen & Callison-Burch (2016), *TACL* 4, 401–415.

    SARI = (F1_add + F1_keep + P_del) / 3        averaged over n-grams n = 1..4

It rewards n-grams correctly added, kept and deleted relative to both the input and the references
(deletion uses precision only). Report the scale (0–1 or 0–100) and implementation used.

*Recommendation:* apply one fixed Arabic normalization (e.g. strip diacritics and tatweel, unify alef
forms) to input, output and references before scoring every system, because surface spelling variants
otherwise count as edits. Pin the implementation so all systems share it.

### BLEU
Measures n-gram overlap with references; an output identical to the input can still score well, so it
is a secondary signal for simplification (Xu et al., 2016). Always report the copy-the-input baseline
next to it.

### BERTScore — weak evidence of meaning preservation
- Khallaf et al. (2022): the lexical system scored BERTScore F1 0.97, yet manual analysis found only
  31 of 299 test sentences correctly simplified.
- Bayan internal result (`../03_project_architecture/pipeline_architecture.tex`): BERTScore F1 had r = −0.014 with human
  equivalence labels (102 annotated pairs, one annotator). This is an internal pilot, not a general
  finding about Arabic.

### PSGI Auto
Essaadani, Ziti & Salah-Eddine (2026), *IJACSA* 17(8). [doi:10.14569/ijacsa.2026.0170871](https://doi.org/10.14569/ijacsa.2026.0170871).
Combines meaning-preservation, terminology-clarity and concision gains; Pearson 0.779 / Spearman 0.755
with human judgments on IT technical texts from three raters. The authors call it an **initial**
validation on a small dataset — optional, not a standard.

### LLM-as-judge
Used by Bayan for semantic equivalence (DSPy). If used in evaluation, the judge should be a different
model from the one that generated the training data, and it should be checked against human labels.
Labeled non-paraphrase pairs from **ArPC** (≈514 train / 189 test negatives) and **APB** (251 negatives)
can test whether the judge ever says "not equivalent".

### What the literature says about metric reliability
| Finding | Source |
|---|---|
| A learned metric (LENS) correlates much better with human judgments of simplification than SARI or BERTScore. It is trained on English only; no Arabic equivalent exists. | Maddela et al., ACL 2023. [arXiv:2212.09739](https://arxiv.org/abs/2212.09739) |
| Widely used automatic metrics **lack sensitivity** for high-quality LLM simplifications; an **error-based human annotation** framework gave more reliable insight. | Wu & Arase, ACM TIST. [arXiv:2403.04963](https://arxiv.org/abs/2403.04963) |
| **Readability measures correlate poorly** with both human judgments and ATS metrics (1,066 features, 8 formulas, English data); **meaning preservation** was the most consistently correlated criterion; the field lacks a coherent construct of "simplification quality". | Cardon & Doğruöz, READIxTSAR @ LREC 2026. [ACL Anthology 2026.readi-1.16](https://aclanthology.org/2026.readi-1.16/) |
| LLMs often produce simplifications **better than the human references**, so reference-based scores can under-rate good systems. | Qiang et al., 2025. [arXiv:2502.08281](https://arxiv.org/abs/2502.08281) |
| Zero-shot LLM prompting for readability assessment outperformed prior unsupervised methods on 13 of 14 datasets across languages; combining LLM and formula scores (LAURAE) was the most robust. | Grossman & Chen, ACL 2026. [arXiv:2604.24470](https://arxiv.org/abs/2604.24470) |
| On Baseet's data, **copying the input scores SARI 39–46**, and the **same outputs score ~8 SARI points higher** with Hugging Face `evaluate` than with Baseet's EASSE-based scoring. | Our re-analysis, `baseet_baseline_analysis.md` |

Practical consequence: no single number is enough. Report a copy baseline, a pinned SARI
implementation, a readability delta, a meaning-preservation check, and a small error-based human
evaluation.

## 3. Readability measurement

### BAREC levels (verified against the BAREC data)

| 19-level | 1–4 | 5–7 | 8–9 | 10–11 | 12–13 | 14–15 | 16–19 |
|---|---|---|---|---|---|---|---|
| 7-level | 1 | 2 | 3 | 4 | 5 | 6 | 7 |

| 19-level | 1–7 | 8–11 | 12–13 | 14–15 | 16–19 |
|---|---|---|---|---|---|
| 5-level | 1 | 2 | 3 | 4 | 5 |

| 19-level | 1–11 | 12–13 | 14–19 |
|---|---|---|---|
| 3-level | 1 | 2 | 3 |

Bayan's pipeline uses the 5-level scale with level 5 dropped: its **"easy" band (levels 1–2) spans
19-level BAREC levels 1–11**, and "hard" (3–4) spans 12–15. Keep this in mind when claiming a
simplification is "easy".

### Formulas
- **AARI** — Al-Tamimi, Jaradat, Al-Jarrah & Ghanim (2014), *International Arab Journal of Information
  Technology* 11(4). Developed with factor analysis on more than 1,196 Jordanian curriculum texts:

      AARI Base = 3.28 × NoC + 1.43 × AWL + 1.24 × ASL
      (NoC = number of characters, AWL = average word length, ASL = average sentence length)

  The formula in the project handoff (4.665 · chars/words + 0.846 · words/sentences − 17.514) is **not**
  the published AARI.
- **OSMAN** — El-Haj & Rayson (2016), LREC 2016, pp. 250–255. [doi:10.63317/5inkeyba57pc](https://doi.org/10.63317/5inkeyba57pc).
  Counts short, long and stress syllables and adds a "Faseeh" factor for script features typical of
  formal Arabic. Available as `textstat.osman()` in Python. Use the library, not a hand-copied formula.

### Neural readability scoring
Use CAMeL Lab's released BAREC models (`CAMeL-Lab/readability-arabertv2-d3tok-reg`, MIT) as an
independent judge of level reduction. Bayan's own MARBERT classifier was used to *filter training data*,
so it should not be the only readability judge of Bayan's outputs. (MARBERT has since been replaced by CAMeL
AraBERT as the pipeline's readability filter, issue #17, so the same caution now applies to that CAMeL model:
evaluate with a different model, for example CAMeLBERT, or with human review.)

## 4. Benchmark protocol for Bayan (*recommendation*)

1. **Test sets with human references:** SAMER test split (evaluation only, under the CAMeL Lab approval);
   a team-verified set of hard BAREC sentences, built the way DAASI was (LLM draft → two annotators
   accept / revise / reject → third resolves disagreements); optionally BALSAM's simplification items,
   ATSC (GitHub `AMahfodh/ArSummarizer`) and DAASI (CC0) as out-of-domain sets.
2. **Systems on the same inputs:** copy-the-input baseline; plain fine-tuned AraT5v2 in Baseet's setup
   (not its hybrid — see `baseet_baseline_analysis.md`); zero-shot LLMs, including one prompted with
   lexical constraints; Bayan's AraT5.
3. **Metrics, one scoring script:** SARI (pinned implementation, fixed normalization, stated scale), BLEU
   as secondary, readability drop via the CAMeL BAREC model, meaning preservation via a judge independent
   of the generator (validated on ArPC/APB negatives), level-control checks (outputs must differ across
   levels), and a small **error-based** human evaluation that counts meaning errors such as negation flips.
4. **Leakage check:** no test sentence (or source document) may appear in training data, and scores must
   never be computed on rows the model trained on.
5. **Report everything,** including results where a baseline wins.

## 5. What we built from this: BayanBench (27–28 Sep 2026)

The protocol above was implemented as **BayanBench** and run on model 2's test split on 28 Sep. The full design,
results and limits are in the final report (Sections 2.5 and 3.3); the points that changed our evaluation are
recorded here with the sources they rest on.

1. **Reference-based scores reward inaction on copy-heavy sets.** Copying scores SARI 77.5 on SAMER test,
   because 48.8% of its pairs are unchanged. Always report the copy baseline and split scores by whether a
   human changed the sentence. SARI correlates only r = 0.36 with human simplicity judgements
   (Alva-Manchego, Scarton & Specia, 2021, *Computational Linguistics* 47(4), doi:10.1162/coli_a_00418).
2. **Score behaviours, not agreement with one editor.** Separate tracks for meaning, ease, restraint, correct
   Arabic, real selections and protected text, scored separately and never averaged, as CheckList-style
   behavioural tests (Ribeiro et al., 2020, *ACL*). Meaning errors follow the insertion / deletion /
   substitution taxonomy of Devaraj et al. (2022, *ACL*, doi:10.18653/v1/2022.acl-long.506) and SALSA
   (Heineman et al., 2023, *EMNLP*, doi:10.18653/v1/2023.emnlp-main.211).
3. **Measure ease with more than one instrument.** Clause length (no clause over 15 words), word familiarity
   (SAMER lexicon levels 4–5) and the CAMeL BAREC readability model. Word frequency is the best-supported
   adaptation for readers with dyslexia (Rivero-Contreras et al., 2021, *Annals of Dyslexia*,
   doi:10.1007/s11881-021-00217-1). The clause measure credits added commas as well as split sentences, so it
   must be read next to the content measures.
4. **Split by document and cluster the intervals.** Sentences from one document pass or fail together, so
   95% intervals come from a bootstrap over whole documents (Miller, 2024, arXiv:2411.00640), and a
   comparison counts only when the paired difference's interval excludes zero.
5. **Test outside the training corpus.** Scores fall away from BAREC test: model 2 (AraT5v2, `[S2]`) fixes
   long clauses in 58.9% of core items but 39.1% of held-out news/legal and 40.4% of text published after
   every corpus we use.
6. **Code checks miss substitutions.** Numbers, negations and kept words catch deletions, but not a reversal
   such as «على الأكثر» → «على الأقل» (at most → at least), which passes every code check. Meaning therefore
   needs a judge tier, and the judge must be validated first: planted errors, self-consistency, and
   acceptance thresholds fixed before any candidate is tested. LLM judges favour outputs close to data they
   wrote or approved (Li et al., 2026, *ICLR*, "Preference leakage").
7. **Benchmark hygiene:** a construct definition, a negative definition (what is out of scope), a locked test
   split and a benchmark card, following Bean et al. (2025, *NeurIPS D&B*, "Measuring what matters") and
   BetterBench (Reuel et al., 2024, *NeurIPS D&B*).
8. **Evaluate the deployed format, not only the checkpoint.** The app's int8 bundles, run through the app's
   own decoding loop, behave differently from the PyTorch model: they send no strength tag and simplify
   less, and int8 pushes AraT5v2 toward copying.
