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
so it should not be the only readability judge of Bayan's outputs.

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
