# Bayan Score: how we measure "dyslexia-friendly"

## Why we need our own metric

There is no benchmark for dyslexia-friendly Arabic text, and none for any language that we could find.

- **SARI** rewards matching a human editor. SAMER's editors mostly swap literary words and almost never
  split sentences. Baseet's references were written by an LLM and are often summaries. So SARI measures
  agreement with a different goal.
- **Readability formulas** are easy to game (Tanprasert & Kauchak, 2021,
  [doi:10.18653/v1/2021.gem-1.1](https://doi.org/10.18653/v1/2021.gem-1.1)).
- **Learned simplification metrics** (LENS, 2023, [doi:10.18653/v1/2023.acl-long.905](https://doi.org/10.18653/v1/2023.acl-long.905))
  and **structural ones** (SAMSA, 2018, [doi:10.18653/v1/n18-1063](https://doi.org/10.18653/v1/n18-1063))
  exist only for English.

The Bayan Score measures our goal directly. It is the share of sentences whose output is **easier for a
dyslexic reader and says the same thing**. SARI stays in the report as the comparison with published work.

## Definition

A sentence **passes** when its output is both easier and faithful.

**Easier.** Every part must hold:

| Check | Rule | Why |
|---|---|---|
| Short sentences | every output sentence has at most 15 words | Long, compound sentences are a known reading barrier |
| Reading level | CAMeL Lab's BAREC readability model puts every output sentence at level 10.15 or easier | The model is trained on 69k human-graded sentences; 10.15 is the median level of sentences SAMER's editors simplified to L3 |
| Complete sentences | AraGPT2 gives each sentence's closing full stop a log-probability of at least −4.96 | Stops "simplifying" by chopping a sentence mid-phrase; 95% of human L3 sentences pass |
| Lighter load | rare + long + morphologically dense + ambiguous word shares do not rise | Each is a text feature that affects dyslexic readers **specifically**; see the next section |

**Same meaning.** Every part must hold:
- LaBSE similarity to the source ≥ 0.733
- at least 87.5% of the source's word count kept
- every number kept
- the same count of negation words
- the source entails every output sentence (mDeBERTa-XNLI, p ≥ 0.028) and contradicts none (p ≤ 0.718)

**Hard rows and copying.** A source that already meets the easier targets passes when its output keeps
meeting them, so copying an easy sentence is fine. The **headline number is the pass rate on hard rows**:
sources that are not easy yet.

**How the thresholds were set.** Every threshold comes from human rewrites (SAMER dev, L5 → L3, using the
5th or 95th percentile), never from a model's output. The 15-word limit is the one choice we made
ourselves; the sensitivity check below shows it does not change the ranking.

## The evidence behind "lighter load"

Each word feature is backed by a study where the effect appeared for readers with dyslexia or reading
disabilities, and not for typical readers:

| Feature | Finding | Source |
|---|---|---|
| Rare words | More frequent words made readers with dyslexia read significantly faster; no effect for controls (eye-tracking, 23 + 23) | Rello et al., 2013, [doi:10.1007/978-3-642-40498-6_15](https://doi.org/10.1007/978-3-642-40498-6_15) |
| Long words | Shorter words improved comprehension for readers with dyslexia; no effect for controls | same study |
| Morphologically dense words | In Arabic, texts with dense words (many attached morphemes) lowered comprehension for children with reading disabilities, not for typical readers (182 fifth-graders). We count attached morphemes per word with CAMeL Tools | *Dyslexia*, 2024, [doi:10.1002/dys.1761](https://doi.org/10.1002/dys.1761) |
| Ambiguous words | Vowels and context affect reading accuracy differently for poor and skilled Arabic readers. We count words with 2+ conflicting readings without tashkeel | Abu-Rabia, 1997, [doi:10.1023/a:1025034220924](https://doi.org/10.1023/a:1025034220924) |

Simplification also helps weaker readers most. In French, 165 second-graders read simplified texts more
fluently and understood them better, and poor readers gained the most (Gala et al., 2022,
[doi:10.1017/s014271642100062x](https://doi.org/10.1017/s014271642100062x)).

## Validation

We could not run a reader study, so the metric is checked against human judgements that already exist,
and against controlled failures.

**1. Does "easier" agree with human readability judgements?** We took 20,000 pairs of BAREC test sentences
whose human-annotated levels differ by 3 or more, and asked which one each measure rates as easier.

| Measure | Agrees with the humans |
|---|---|
| Words in the longest sentence | 80.2% |
| The Bayan Score's "easier" rule (14,666 pairs where it tells them apart) | **93.1%** |

**2. Does it follow graded human rewrites?** On SAMER test, the readability model rates L3 easier than L5
in 77.9% of the rows the editors changed. The mean levels are L5 10.80, L4 10.58 and L3 10.31.

**3. Does "same meaning" separate faithful from broken rewrites?** Human rewrites (SAMER test, L5 → L3)
are judged faithful 85.2% of the time. We then corrupted those same rewrites on purpose and measured how
many the metric rejects:

| Corruption | Caught |
|---|---|
| Output cut to its first 40% | 99.7% |
| A negation inserted | 99.3% |
| An unrelated sentence added | 77.0% |
| Two content words swapped for words from another sentence | 65.2% |

**4. Can it be gamed?** We ran cheating outputs on the 3,779 BAREC test sentences that are not easy yet:

| Cheat | Pass rate |
|---|---|
| Copy the input | 0.0% |
| Keep the first half | 0.0% |
| Chop at random points into three "sentences" | 2.9% |
| Shuffle the words | 2.1% |

**5. Is it achievable, and are the choices stable?** On SAMER test's hard rows, SAMER's own human L3
rewrites score **15.0%**. Most of them keep the original sentence length and reading level: 76% stay above
the target level. That is expected, because SAMER was written to simplify vocabulary, not for dyslexia.

The ranking stays the same (copy 0% < SAMER human 15–16%) when the level target moves to the 75th or
90th percentile of human L3 sentences. It also stays the same when the length limit moves between 10 and
20 words (SAMER human 13.4% to 15.0%, copy 0% throughout).

## Limits

- **No dyslexic readers in the loop.** The metric measures text features that research shows dyslexic
  readers are sensitive to, not reading performance. A reader study is the missing step.
- **Subtle meaning errors slip through.** A swapped content word is caught only 65% of the time.
- **The reading-level model is not dyslexia-specific.** It is trained on general grade levels; the
  dyslexia-specific part is the word load.
- **The thresholds come from SAMER's literary register.** They may need checking on other kinds of text.
