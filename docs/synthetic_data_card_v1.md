---
language:
- ar
license: cc-by-sa-4.0
license_name: cc-by-sa-4.0
license_link: https://creativecommons.org/licenses/by-sa/4.0/
task_categories:
- text-generation
tags:
- arabic
- text-simplification
- dyslexia
- synthetic-data
- barec
size_categories:
- 10K<n<100K
pretty_name: Bayan Synthetic Simplification Corpus
---

# Synthetic simplification data card — v1

Version 1 of `bayan-simplification-corpus`: every non-test BAREC hard-band sentence (levels 3–4)
regenerated with a self-hosted generator and a judge from a different model family, under the rules
from issue #44, plus a readability bar of **at least two CAMeL levels easier** than the source.

## What changed from v0 (changelog)

| | v0 (DeepSeek) | v1 |
|---|---|---|
| Source pool | ~20% stratified sample of the hard band | the **whole** non-test hard band (23,221 sources) |
| Generator | DeepSeek V4.1 Flash | Gemma 4 31B (`google/gemma-4-31B-it-qat-w4a16-ct`) |
| Judge | DeepSeek V4.1 Flash (same model as the generator) | Qwen3.8 27B (`RedHatAI/Qwen3.8-27B-INT4`), a different model family |
| Meaning threshold | 0.70 | **0.85** (tier A only); the new judge was recalibrated and 0.75 is its floor (below) |
| Readability gate | P(easy) rise ≥ 0.33 logit | **hardest-sentence CAMeL lead ≥ 2.0 levels** (below) |
| Winner | highest `ease_score` among passers | the largest readability lead among candidates passing every gate |
| Diacritics | kept from the source (13.8% of targets vowelled) | **stripped everywhere**, both sides |
| Quiz / multiple-choice items | kept, 9.7% collapsed their options into prose | kept; option labels must survive in order (code gate) |
| Sources of 5 words or fewer | rewritten (8.1%) | **never rewritten**: `short` identity pairs |
| Scripture, Hanging Odes, verse quotes | Quran/Hadith/Bible sources protected; verses quoted inside other text paraphrased | also Hanging Odes, any row with a verse marker, and every source a validated classifier labels classical poetry / Quran / hadith: `protected` identity pairs |
| Honorifics | dropped in 103 pairs | must survive (code gate) |
| Cut-off sources (ending «،» «؛» «:» or no mark) | completed with a full stop (22.4%) | the rewrite ends the way the source does (normalization) |

## Pair types

| `pair_type` | what | output |
|---|---|---|
| `generated` | a simplification that passed every gate | rewritten |
| `identity` | easy-band (BAREC level 1–2) sentences with the lowest age-of-acquisition vocabulary, domain- and length-matched to the generated set | = input |
| `protected` | scripture, classical poetry, quoted verses | = input |
| `short` | 5 words or fewer (headings, labels, cut half-lines), distinct texts | = input |

**The mix is set for training a simplification model: ~70% generated, ~30% identity-type.** Generated pairs
are the only rows that teach how to simplify, so all of them are kept. Identity-type rows teach when not
to rewrite. Copying is the cheapest thing for a seq2seq model to learn, so too many of them pull it toward
under-simplifying; v1's generated pairs contain no near-copies (every one is at least two levels easier),
which leaves room for ~30%.
- `identity` gets the largest identity share because it is the most informative no-op example: it matches
  the generated set on length and domain, so difficulty is the only cue. It stops at 2,483 rather than a
  higher target because genuinely easy text is short; filling the long-sentence bins from shorter ones
  would teach "long means rewrite".
- `protected`: every Quran row, every Hanging Odes line, and every verse or poem found inside another
  source (the hardest case to recognize) are kept; Hadith is capped at 250 and the Bible at 150.
- `short`: ~740 distinct texts are enough for a pattern the model can read off length alone.

Report evaluation metrics per `pair_type`: SARI / BLEU on `generated`, exact-match copy rate on the rest.

## Counts

| `pair_type` | train | dev | test | total | share |
|---|---|---|---|---|---|
| generated | 8,236 | 1,048 | 1,098 | 10,382 | 69.3% |
| identity | 1,939 | 260 | 284 | 2,483 | 16.6% |
| protected | 1,147 | 137 | 89 | 1,373 | 9.2% |
| short | 613 | 59 | 65 | 737 | 4.9% |
| **total** | **11,935** | **1,504** | **1,536** | **14,975** | |

Generated-pair funnel: 23,221 hard sources → 23,205 with a usable generator response → 10,693 accepted
at meaning ≥ 0.85 and lead ≥ 2.0 → 10,382 after the classifier moved poetry / Quran / hadith sources to
`protected` and texts near-duplicating a BAREC-test sentence (5+ words, ≥ 0.8 overlap) were dropped.
Tier B (meaning 0.75–0.85, 1,220 more sources) is not shipped: an audit found it carried nearly three
times the minor-loss rate of tier A (37.6% vs 13.4%, below).

## How a generated pair is accepted

1. **Routing.** Only non-test BAREC level 3–4 sentences of more than 5 words that are not protected reach
   the generator.
2. **Generation.** Gemma 4 writes 5 candidates per source (`SimplifyToEasyArabic` + `STRONG_SIMPLIFICATION`
   prompt). The prompt states the #44 rules: keep MCQ options, copy verses, keep honorifics, end a cut-off
   piece the same way, no tashkeel.
3. **Normalization** (`scripts/corpus_constraints.py`). Tashkeel stripped, the source's ending mark applied.
4. **Structure gates** (code). MCQ option labels in the same order; every honorific kept; every ﴿…﴾ verse
   verbatim. A candidate failing any of these is discarded before judging.
5. **Readability gate.** CAMeL (`CAMeL-Lab/readability-arabertv02-word-CE`, 19 levels) expected level of the
   source (scored whole, as BAREC annotates it; MCQs on the question stem) minus that of the rewrite's
   **hardest sentence** must be **≥ 2.0**. CAMeL is a sentence-level model: scoring a multi-sentence
   rewrite as one text reads four short sentences like one long one and hides the gain from splitting
   (rewrites of 4+ sentences passed 0.8–2.1% of the time under whole-text scoring). Taking the *hardest*
   sentence keeps one hard sentence from hiding behind easy ones. `readability_lead_whole` keeps the
   whole-text lead for reference.
6. **Meaning gate.** The Qwen judge scores each remaining candidate 0–1; **≥ 0.85** passes (tier A).
   The run logged everything ≥ 0.75, so tier B can be re-applied from the checkpoints.
7. **Winner.** The candidate with the largest readability lead.

### Judge calibration (Qwen3.8 27B)

Scored on 112 originals × 5 planted variants and 300 human-labelled pipeline pairs
(`scripts/calibrate_judge.py`):

| threshold | faithful | added claim | deleted content | negation | question | human "same" | human "changed" |
|---|---|---|---|---|---|---|---|
| 0.70 | 99% | 19% | 44% | 1% | 0% | 90% | 16% |
| **0.75** | 99% | 15% | 21% | 1% | 0% | 90% | 16% |
| 0.85 | 99% | 10% | 12% | 1% | 0% | 86% | 16% |

0.75 is the lowest threshold at which Qwen accepts fewer planted additions and deletions than the v0
DeepSeek judge did at 0.70 (34% / 25%). v1 ships at 0.85, which halves both.

### Protected-text classifier

`scripts/classify_protected.py` (Qwen3.8) labels each source prose / classical_poetry / quran / hadith.
Validated on BAREC rows whose Source already gives the answer: classical poetry 95/100, Quran 100/100,
hadith 55/100 (the rest of BAREC's Hadith source is largely narration chains and commentary, labelled
prose), prose wrongly protected 2/300.

## Quality

Generated pairs (10,382):

| | value |
|---|---|
| readability lead, hardest sentence (the gate) | mean 3.05, median 2.86 CAMeL levels |
| CAMeL level, source → hardest rewrite sentence | 12.4 → 9.3 (BAREC's easy band is ≤ 11) |
| readability lead, rewrite scored as one text | mean 1.48 |
| meaning score (Qwen judge) | mean 0.893; all tier A (≥ 0.85) |
| length, rewrite / source (words) | median 0.88; 16.5% longer than the source (splitting adds words) |
| sentences per rewrite | 1: 2,162 · 2: 3,561 · 3: 2,686 · 4: 1,241 · 5+: 732 |
| multiple-choice items | 1,095 (every option kept, in order) |

`scripts/check_corpus.py` reports **0 violations** on the export: no tashkeel anywhere, identity-type rows
unchanged, and in every generated pair the MCQ options, honorifics and quoted verses kept, the source's
ending preserved, tier A, and lead ≥ 2.0. `scripts/check_leakage.py` finds no train sentence sharing a
5+-word match with BAREC-test.

**Meaning audit.** A blind read of a 10% random sample (1,156 generated pairs, drawn before tier B was
dropped), labelling each rewrite *same meaning*, *minor loss* (a dropped qualifier, name or hedge) or
*changed* (a different claim):

| | pairs | same | minor loss | changed |
|---|---|---|---|---|
| tier A (shipped) | 1,039 | 84.9% | 13.4% | **1.7%** |
| tier B (not shipped) | 117 | 59.8% | 37.6% | 2.6% |

The false-accept rate for real meaning changes is about 1.7% (95% CI roughly 1.1–2.7%), under the 5%
target. The judge's score barely separates the classes (mean 0.884 on *same*, 0.871 on *changed*), so a
higher threshold would not remove these errors. Most are generator misreadings the judge cannot see:
a qualifier's scope ("activity on religious grounds is banned" → "political activity is banned"), a
reversed legal condition, a mistranslated word ("linens" → "white papers"), a swapped speaker.

**Human review.** A random sample of 147 tier-A generated pairs is in `data/processed/review_v1/`, in
random order. If reviewers find no clear meaning error in the first 58, the false-accept rate is below 5%
with 95% confidence; none in all 147, below 2%.

## Reproducing

```
uv run python scripts/barec_simplification_pipeline.py --backend vllm --all --prompt strong \
    --eq-threshold 0.75 --concurrency 64 --checkpoint data/processed/barec_hard_v1_checkpoint.jsonl
# (the run logs every candidate at eq >= 0.75; assembly re-selects at the tier-A threshold 0.85)
uv run python scripts/rescore_sentencewise.py data/processed/barec_hard_v1_checkpoint.jsonl
uv run python scripts/judge_pending.py data/processed/barec_hard_v1_checkpoint.pending_judge.jsonl
uv run python scripts/classify_protected.py --ids <accepted source IDs>
uv run python scripts/assemble_corpus_v1.py data/processed/barec_hard_v1_checkpoint.jsonl \
    --sentencewise data/processed/barec_hard_v1_checkpoint.sentencewise.jsonl \
    --judged data/processed/barec_hard_v1_checkpoint.pending_judge.judged.jsonl \
    --protected-labels data/processed/protected_labels.jsonl
uv run python scripts/check_corpus.py data/processed/corpus_v1      # must report 0 violations
```

Models are served with `scripts/remote/serve_vllm.sh` (vLLM ≥ 0.17; the run used the
`vllm/vllm-openai` image, vLLM 0.30). The whole run cost about $6.40 of rented GPU time (2×A40 for
generation, 1×RTX A6000 for the second judging pass and the classifier).

## Known limits

- **Readability is one model's opinion.** The gate relies on CAMeL alone. v0's human audit found 20% of
  accepted pairs "not genuinely simpler"; v1's ≥ 2-level bar targets that, but it has not yet been
  re-measured by people.
- **Minor nuance loss.** About 13% of generated pairs drop a qualifier, name or hedge, and about 1.7%
  change the meaning (audit above). These figures come from one reader and need confirmation by the
  human review (`data/processed/review_v1/`).
- **A stricter prompt helps, but at a cost (tested for v2).** Re-running 304 audited sources with a
  faithfulness-first prompt (`--prompt strict`) cut the estimated meaning-change rate to ~0.5% and the
  minor-loss rate to ~11%, but kept ~19% fewer pairs. It did not fix the misreadings listed above; the
  same errors came back word for word. Results: `data/processed/ab_strict/`.
- **Judge list mismatch.** When the judge returns one reason for several candidates, only the first
  candidate is kept (seen on ~8% of sources in the A/B). This loses yield, not quality; fix planned for v2.
- **The hardest-sentence measure trusts sentence splitting.** A rewrite chopped into fragments could
  score well on readability; the meaning judge and the human review are the checks on fluency.
- **The judge is strict on synonyms.** Reading rejected pairs suggests about half of those rejected on
  meaning alone (4.7% of sources) are acceptable rewrites the judge scored low for ordinary word swaps.
- 16 sources returned malformed generator output on every attempt and 15 malformed judge output; they
  are absent.
- Every candidate, its scores and the judge's reasoning are logged in the checkpoints, so the gate can be
  re-applied at other thresholds without regenerating.
