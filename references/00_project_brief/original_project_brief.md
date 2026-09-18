# Project Brief — Arabic Dyslexia-Friendly Text Simplification Assistant

I'm developing this as a candidate idea for a Samsung Innovation Campus (SIC) capstone project, and I want to explore and flesh it out on my own before presenting it to my 6-person team. Please treat this as full context — help me continue designing and validating this project from here.

## Program context
- This is for a Samsung-sponsored AI capstone program (references to "on-device AI" and submitting work "to SIC" — Samsung Innovation Campus). Judging appears to reward "Pure AI" ideas with clear, available data, and past winning cohort projects have skewed toward accessibility/humanitarian problems (e.g. a "Speech Emotion Synthesis" project placed 2nd in a past cohort).
- My team already has several other candidate ideas in play (an AI waste-management app with a working prototype, an accessible-camera-guidance app for blind users, a RAG-based curriculum assistant for blind students, etc.), built around a partner accessibility organization ("Al-Noor") the team has real interviews with (two named students, Noor and Ahmed, gave real field-validated problem statements for other ideas).
- **Timeline:** the actual 3-week build sprint starts next week. There is currently one free "week 0" available before the clock starts, useful for resolving any external dependency before it costs build time.
- Unlike the blind-accessibility ideas, this dyslexia-focused idea currently has **no partner organization or real interview subject** lined up — that's the single biggest gap to close, ideally during week 0.

## The problem
Dyslexic and cognitive-accessibility readers can see text fine but struggle to process it: long compound sentences, low-frequency vocabulary, dense material. Arabic adds specific extra difficulty beyond what most (Latin-script-first) dyslexia tools address:
- **Missing diacritics (tashkeel):** everyday Arabic text omits vowel marks; fluent readers infer pronunciation from context, a skill dyslexic readers often lack, making word recognition harder.
- **Agglutinative morphology:** prefixes/suffixes attach directly to the word with no spaces, so one visual "word" can pack in what would be 3–4 separate words in English.
- **Connected script:** letterforms change shape by position in a word, compounding letter-confusion issues.
- Confirmed via research: no working dyslexia-friendly Arabic typeface is currently public, and no deployed Arabic dyslexia software was found.

## Proposed solution — 3-stage pipeline
1. **Simplify** — input Arabic text (typed/pasted, or OCR'd from a photo, optionally reusing a Tesseract OCR step) goes through a simplification model that shortens compound sentences and swaps low-frequency vocabulary for common synonyms while preserving meaning.
2. **Diacritize** — run simplified output through automatic diacritization (tashkeel) so the reader can sound words out correctly.
3. **Read aloud, synced** — Arabic TTS reads the text with word-by-word highlighting synced to the audio (karaoke-style), a well-established multi-sensory reading-support technique.

## Data sources identified
- **SAMER Arabic Text Simplification Corpus** (arXiv:2404.18615) — parallel complex↔simple Arabic sentence pairs, purpose-built for this task. Removes the "no training data" risk entirely.
- **A companion fine-grained Arabic readability assessment corpus** (arXiv:2502.13520), likely from the same research group — not for training, but for reporting a quantified readability-improvement score in the eventual pitch.
- **Tashkeela** — diacritization dataset, already scoped by my team for a separate (shelved) Libyan-dialect idea; directly reusable here for stage 2.
- Related prior work to be aware of / cite: research on automatic correction of Arabic dyslexic text, and dyslexia-friendly Arabic typeface design research (both confirm the gap but show some groundwork exists — I should cite this work, not claim to be first).

## Model architecture decision (already discussed and settled)
**Deployed model: fine-tune a seq2seq model (AraT5) for the simplification step**, not a decoder-only open-source Arabic SLM. Reasoning:
- Text simplification is a transduction task (input→transformed output, same meaning) — the native fit for encoder-decoder architectures, which tend to stay more tightly grounded to the source than decoder-only generation. Faithfulness matters a lot here — silently distorting meaning for a vulnerable reader is a real harm, not just a quality bug.
- There's direct precedent: the AraT5-MSAizer paper (ACL Anthology, 2024.osact-1.16) used AraT5 for an architecturally similar dialect→MSA transformation task.
- Seq2seq models in this family are far smaller than modern SLMs — faster to fine-tune on limited compute/time, and much easier to quantize and run **on-device**, matching the program's stated on-device AI interest.
- Considered and rejected as the *deployed* model: fine-tuning an open-source Arabic SLM (e.g. Jais, ALLaM, SILMA, or general multilingual models with decent Arabic coverage like Qwen/Gemma). These have stronger out-of-the-box fluency but are heavier to deploy and more prone to "assistant drift" (added explanation, looser rephrasing, hallucination) unless heavily constrained — undesirable for a faithfulness-critical task.

**Data augmentation:** use a strong existing Arabic-capable LLM (API-based) purely to generate synthetic complex→simple training pairs, to augment SAMER if it proves too small. This model is not deployed — it's only a data-generation tool.

## Quality-control pipeline (settled design — LLM-as-judge + DSPy)
The open-source SLM I considered for deployment is repurposed instead as an **evaluation/filtering judge**, never shipped on-device:
1. **Data generation** — big LLM generates synthetic complex→simple pairs.
2. **Data filtering** — a DSPy-optimized judge scores each synthetic pair for semantic equivalence between original and simplified text; low-scoring pairs are rejected before they enter training data.
3. **Training** — fine-tune AraT5 on filtered real (SAMER) + synthetic pairs.
4. **Eval** — run the same judge on a held-out test set and report an average equivalence score as the headline faithfulness metric (stronger than BLEU/ROUGE, which reward word overlap, not meaning preservation).
5. **(Optional) Runtime gate** — score live output before showing it to a user; fall back to original text with a note if the score is too low, rather than silently showing a possibly-distorted simplification. Echoes a "trust signaling" feature already used in a separate team idea (a RAG curriculum assistant that cites its sources).

**DSPy specifics:** define a signature — inputs `original_text`, `simplified_text` → outputs `equivalent` (bool or 1–5 score) and `rationale`. Use an optimizer (BootstrapFewShot or MIPROv2) to compile the judge prompt against a small hand-labeled validation set, rather than hand-writing/eyeballing the judge prompt.

**Two open implementation risks, not yet resolved:**
1. Need to hand-label ~30–100 (original, simplified, correct verdict) triples before DSPy can optimize anything — SAMER's human-written simplifications give free "positive" examples; "negative" (meaning-distorted) examples need to be manually created (e.g. deliberately corrupting some pairs).
2. Unverified whether a small SLM judges Arabic semantic equivalence reliably enough — since the judge doesn't need to run on-device or in real time, it's not actually constrained to a small model; should pilot both a small SLM and the larger data-generation LLM as judge candidates against the hand-labeled set and see which one actually agrees with human judgment before committing to one.

## Open items to resolve before/during week 0
- Find a real field-validation partner (a school, a learning-disabilities org, or individual dyslexic Arabic readers) — the credibility gap versus the team's other Al-Noor-backed ideas.
- Hand-label the DSPy validation set.
- Confirm SAMER's actual size/coverage to judge whether synthetic augmentation is actually necessary.
- Decide on OCR input scope (MVP could just accept pasted/typed text and defer OCR).
- Pick a specific Arabic TTS engine/model for the read-aloud stage.

## What I want help with next
Continue from here — help me build out the technical plan in more depth (e.g., concrete AraT5 fine-tuning setup, DSPy program structure, TTS engine selection, a week-by-week execution plan), and/or help me prepare the pitch materials to present this to my team.
