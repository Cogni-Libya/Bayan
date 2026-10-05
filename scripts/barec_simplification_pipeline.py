"""BAREC hard/easy simplification pipeline (2% pilot).

Builds the training-pair dataset described in the pipeline report's Stage 1
design:

1. Load BAREC (train+dev+test), keep only needed columns, drop level 5
   (2.6% of the corpus, only 6.9% of its Specialized content -- see the
   report for the full justification).
2. Take a fair (stratified) sample by difficulty level from the pool.
   No prose-quality filtering: fragments, headers, dates, and citations are
   real content a reader encounters, and the two downstream mechanisms
   already handle them correctly on their own -- identity pairs are safe by
   construction (output = input, whatever the input is), and the hard-band
   generator's output is gated by the two validators regardless of whether
   the anchor was a full sentence or a fragment.
3. Split the sample into easy (levels 1-2), hard (levels 3-4), and scripture
   (Quran/Hadith/Old Testament/New Testament by BAREC's Source tag) --
   scripture is routed out regardless of its assessed level: canonical text
   is preserved verbatim, not simplified because it happened to score easy.
   Known gap: this catches BAREC's document-level tagging, not a quotation
   embedded inside some other source's text.
4. Easy and scripture -> identity pairs. No generation, no cost, no risk.
5. Hard -> one DSPy Generator call producing NUM_CANDIDATES candidate
   rewrites, one DSPy equivalence-validator call scoring all of them
   against the original (0.0-1.0 each), and two local (no API call) scoring
   passes -- CAMeL readability (how much easier each one is than the
   original) and lexical difficulty (AoA + word length) -- 2 LM calls per
   hard sentence total, not NUM_CANDIDATES*3. Candidates whose P(easy) rose
   by at least TAU over the original AND that score above
   EQUIVALENCE_THRESHOLD outrank ones that don't; among those, the
   easiest-vocabulary one is kept, not the most faithful one (faithfulness
   is already assured by clearing EQUIVALENCE_THRESHOLD). This happens even
   when none of the NUM_CANDIDATES attempts fully pass (same downstream
   `passed` filter as always). See simplify_and_validate()'s docstring for
   the full ranking rule and the TSAR 2025/EhiMeNLP precedent behind
   generate-then-rerank.

Usage:
    uv run python scripts/barec_simplification_pipeline.py
    uv run python scripts/barec_simplification_pipeline.py --dry-run
    uv run python scripts/barec_simplification_pipeline.py --sample-fraction 0.05

Needs DEEPSEEK_API_KEY set (directly, or via a project-root .env file --
see .env.example) for anything past --dry-run.

Not run by anything automatically -- this script makes real, costed API
calls once past the dry-run stage. Run it yourself when ready.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# numpy/onnxruntime must be imported before dspy: dspy's lazy-import machinery, if it runs first,
# corrupts numpy's own C-core initialization (TypeError: data type 'bool' not understood) in a way
# that then breaks onnxruntime's internal numpy dependency too.
import numpy as np
import onnxruntime
import dspy
import polars as pl
from dotenv import load_dotenv
from tqdm import tqdm

from camel_readability import CamelReadability
from corpus_constraints import (
    has_verse_marker, is_short, mcq_stem, normalize_candidate, readability_units, strip_tashkeel, structure_gates,
)
from lexical_scorer import DIAC, TOKEN, LexicalScorer
from validation import TAU, load_readability_classifier, score_readability

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BAREC_DIR = PROJECT_ROOT / "data" / "raw" / "barec"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Every successful hard-band result is appended here immediately (one JSON object per line,
# flushed to disk right away) -- not held in memory until the whole run finishes. A run that
# gets interrupted (crash, hang, laptop sleep killing the connection) keeps everything already
# processed, and re-running the script picks up where it left off instead of starting over.
HARD_CHECKPOINT_PATH = PROCESSED_DIR / "barec_hard_v1_checkpoint.jsonl"  # v0 (DeepSeek) is barec_hard_pilot_checkpoint.jsonl

# Superseded by the local CAMeL readability model (camel_readability.py, loaded once in
# configure_dspy() and reused for every candidate: no API call, no per-candidate cost, and it
# can't parse-fail the way an LLM response can). Kept for reference/comparison --
# ClassifyReadabilityLevel and optimize_level_classifier.py still work standalone, just no longer
# wired into this pipeline's configure_dspy().
COMPILED_LEVEL_CLASSIFIER_PATH = PROJECT_ROOT / "scripts" / "compiled" / "level_classifier.json"

# Produced by optimize_equivalence_validator.py, which compiles CheckSemanticEquivalence
# against human-annotated ground truth via MIPROv2 -- loaded automatically below if present.
COMPILED_EQUIVALENCE_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "compiled" / "equivalence_validator.json"

DEEPSEEK_MODEL = "deepseek/deepseek-flash"  # DeepSeek V4.1 Flash's current API model id; the
# legacy "deepseek-v4-flash" alias still works but routes here.

# --backend vllm: self-hosted OpenAI-compatible servers, one model per GPU. The generator and the judge
# are different model families on purpose -- a model grading its own rewrites was measured to pass far
# more content-dropping candidates (references/04_dataset_construction, part 5).
VLLM_GENERATOR_MODEL = "google/gemma-4-31B-it-qat-w4a16-ct"
VLLM_JUDGE_MODEL = "RedHatAI/Qwen3.8-27B-INT4"

KEEP_COLS = [
    "ID", "Sentence", "Word_Count", "Readability_Level_5", "Readability_Level_19", "Domain", "Source", "Text_Class",
    "barec_split",
]  # barec_split ("train"/"dev"/"test", tagged in load_and_clean_barec) labels every row's origin
# instead of silently filtering it -- callers decide their own train/dev/test policy explicitly.
# See barec_provenance.py for the same idea applied to already-generated data, including
# cross-split-duplicate detection (a train row's text can still match test under a different ID,
# which this column alone doesn't catch). Readability_Level_19 is the gold, non-predicted BAREC
# level, kept for per-source audit stratification that doesn't depend on this pipeline's own
# predictions.

# This pipeline's readability scale is BAREC's 5-level collapse with level 5 dropped, so 4
# levels remain (1 = simplest ... 4 = hardest). This is NOT BAREC's native 19-level scale --
# don't conflate the two when reading or editing the prompts below.
EASY_LEVELS = (1, 2)
HARD_LEVELS = (3, 4)
EASY_LEVEL_CEILING = 2  # `is_easy` = predicted_level <= this; informational for generated pairs (the gate is the rise in P(easy))

# CheckSemanticEquivalence outputs a continuous 0.0-1.0 score, not a boolean -- this threshold is
# what simplify_and_validate() uses to derive the pass/fail gate and to break ties among reranked
# candidates. Calibrated via a threshold sweep against a held-out annotated set (0.70-0.75 was a
# broad, stable optimum); picked the lower/safer edge of that plateau rather than the exact peak,
# since the sweep set is small -- treat as directional, revisit with more annotations.
EQUIVALENCE_THRESHOLD = 0.7

# Both gates passing (equivalent AND readability_passed) is necessary but not sufficient to rule
# out fluent-but-unfaithful output: human labeling found holistic readers miss fluent meaning
# changes far more often than crude/mechanical ones, and a winner sitting right at
# EQUIVALENCE_THRESHOLD is exactly the population that blind spot hits hardest.
# TIER_A_EQ_THRESHOLD raises the bar for "confidently trainable" data without a separate
# claim-coverage judge -- cheap insurance against a known failure mode, not a new faithfulness
# measurement. Tier B (both gates pass, eq in [0.70, 0.85)) is backfill-only, an assembly-time
# decision made downstream of this pipeline; this module only records which tier a winner falls
# in. Tier C is any candidate that fails either gate -- flagged, never training data.
TIER_A_EQ_THRESHOLD = 0.85


def acceptance_tier(equivalent: bool, readability_passed: bool, equivalence_score: float) -> str:
    if not (equivalent and readability_passed):
        return "C"
    return "A" if equivalence_score >= TIER_A_EQ_THRESHOLD else "B"


# Reranking among already-valid candidates (see simplify_and_validate's ranking rule): fitted by
# logistic regression on 8,310 real SAMER full-sentence human-simplification pairs (L5 vs L3 of the
# same underlying sentence, data/processed/readability_compare_inputs/samer_train.parquet --
# `scripts/fit_ease_score_weights.py`), predicting which of a pair's two texts is the easier one
# from CAMeL logit(P(easy)) and mean AoA. Held-out (5-fold CV) recall at a ~10% reversed-pair
# false-accept rate: CAMeL alone 59.6%, this combination 75.1%. Fit on SAMER's TRAIN split, not
# test -- an earlier version of this formula was fit on samer_test.parquet, which is the project's
# own locked eval set (data/test_manifest.json); found and fixed in review. Full derivation and
# data provenance: pipeline_architecture.tex Section 4.
EASE_W_CAMEL_LOGIT = 0.1121
EASE_W_MEAN_AOA = -0.5777
EASE_INTERCEPT = 1.7292
EASE_FORMULA_VERSION = "samer_train_2feat_v3"  # bump whenever the weights above change -- logged
# per row so an audit or ablation can tell which formula version produced a given result. v2 (this
# constant's prior value, "samer_fullsentence_2feat_v2") was fit on the locked SAMER test split;
# retired, not reused.

# Reranking: generate this many candidate simplifications per hard sentence and keep the
# best-scoring one, instead of generating once and gating pass/fail -- informed by the TSAR 2025
# Shared Task's winning system (EhiMeNLP: generate multiple candidates, then rerank by
# readability + semantic similarity, no parallel training data required). Real cost multiplier:
# NUM_CANDIDATES generations + NUM_CANDIDATES x 2 validations per hard sentence, i.e. 5x the
# call volume (and $ cost) of the original single-candidate pipeline.
NUM_CANDIDATES = 5

# A rewrite must be at least this many CAMeL levels (expected level on the native 19-level scale) easier
# than its source to count as a simplification at all.
MIN_READABILITY_LEAD = 2.0
SELECTION_RULE = "v1: structure gates, eq>=threshold, lead>=MIN_READABILITY_LEAD; then eq>=tierA, max lead, eq"
# Logged per row; configure_dspy() sets them to the models actually serving the run.
GENERATOR_MODEL_ID = DEEPSEEK_MODEL
JUDGE_MODEL_ID = DEEPSEEK_MODEL
PROMPT_VARIANT = "base"

# Scripture and classical poetry come back unchanged in the app, so the model must never learn to
# paraphrase them: routed as identity pairs regardless of assessed difficulty. BAREC tags these by
# Source; a verse quoted inside some other source's text is caught separately by
# corpus_constraints.has_verse_marker (see route_of).
PROTECTED_SOURCES = {"Quran", "Hadith", "Old Testament", "New Testament", "Hanging Odes"}

# Every BAREC row gets exactly one route (column `route`, set in load_and_clean_barec):
#   protected -- PROTECTED_SOURCES, or any row quoting a verse          -> identity, pair_type "protected"
#   short     -- SHORT_MAX_WORDS words or fewer (headings, labels, cut half-lines) -> identity, "short"
#   easy      -- levels 1-2                                               -> identity candidates
#   hard      -- levels 3-4                                               -> the generator
ROUTES = ("protected", "short", "easy", "hard")


# --------------------------------------------------------------------------------------
# Data loading / cleaning / sampling
# --------------------------------------------------------------------------------------


def route_of(source: str, sentence: str, level: int) -> str:
    if source in PROTECTED_SOURCES or has_verse_marker(sentence):
        return "protected"
    if is_short(sentence):
        return "short"
    return "easy" if level in EASY_LEVELS else "hard"


def load_and_clean_barec() -> pl.DataFrame:
    """All three BAREC splits, level 5 dropped, tashkeel and tatweel stripped from every sentence (the
    app strips them before simplifying, so no pair should carry them on either side; CAMeL's input
    variant drops them anyway, so readability scores are unaffected), and a `route` per row."""
    splits = [
        pl.read_csv(BAREC_DIR / f"{name}.csv", encoding="utf8-lossy").with_columns(pl.lit(name).alias("barec_split"))
        for name in ("train", "dev", "test")
    ]
    df = pl.concat(splits).select(KEEP_COLS)
    df = df.filter(pl.col("Readability_Level_5") != 5)
    df = df.with_columns(pl.col("Sentence").map_elements(strip_tashkeel, return_dtype=pl.Utf8))
    return df.with_columns(
        pl.struct(["Source", "Sentence", "Readability_Level_5"])
        .map_elements(lambda r: route_of(r["Source"], r["Sentence"], r["Readability_Level_5"]), return_dtype=pl.Utf8)
        .alias("route")
    )


def stratified_sample(df: pl.DataFrame, fraction: float, seed: int) -> pl.DataFrame:
    """Fair (proportional-to-natural-frequency) sample, stratified by level."""
    return df.group_by("Readability_Level_5", maintain_order=True).map_groups(
        lambda g: g.sample(fraction=fraction, seed=seed)
    )


def build_identity_pairs(rows: pl.DataFrame, pair_type: str) -> pl.DataFrame:
    """pair_type is "identity" for the easy band (genuinely simple, no generation needed) or
    "scripture" for canonical text preserved regardless of assessed difficulty -- is_easy
    reflects the row's actual level either way, not forced True, since a scripture row can be
    level 3-4 and still correctly be an identity pair for a different reason."""
    return rows.select(
        pl.col("ID"),
        pl.col("Sentence").alias("original_text"),
        pl.col("Sentence").alias("simplified_text"),
        pl.col("Readability_Level_5").alias("source_level"),
        pl.col("Readability_Level_5").alias("predicted_level"),  # identity: known, not classified
        pl.lit(True).alias("equivalent"),
        pl.lit("identity pair -- no generation or judgment needed, output equals input").alias("equivalence_reasoning"),
        (pl.col("Readability_Level_5") <= EASY_LEVEL_CEILING).alias("is_easy"),
        pl.lit(pair_type).alias("pair_type"),
    )


# --------------------------------------------------------------------------------------
# The readability check is the shared CAMeL model in camel_readability.py, scored through
# validation.score_readability(): GPU (torch) or cached ONNX on CPU, each text on its own.
# --------------------------------------------------------------------------------------


# --------------------------------------------------------------------------------------
# DSPy signatures
#
# A dspy.Signature's docstring IS the task instruction DSPy compiles into the actual
# prompt; each field's `desc` is the per-field guidance. CheckSemanticEquivalence is
# MIPROv2-compiled against human-annotated ground truth (optimize_equivalence_validator.py);
# ClassifyReadabilityLevel is defined here for reference/comparison but no longer wired into
# this pipeline (see COMPILED_LEVEL_CLASSIFIER_PATH's comment). Both the generator and the
# equivalence validator score/generate NUM_CANDIDATES items per call, not one -- see each
# signature's own docstring for why.
# --------------------------------------------------------------------------------------


class SimplifyToEasyArabic(dspy.Signature):
    """Rewrite a Modern Standard Arabic sentence so it is easy for a dyslexic
    or lower-literacy reader to read, while preserving its exact meaning --
    producing NUM_CANDIDATES independently-valid candidate rewrites in one
    pass, not just one. Generating several different attempts and having a
    downstream step pick the best one (by semantic equivalence and actual
    reading level) beats generating a single attempt and simply accepting
    or rejecting it -- the same candidate-generation-then-rerank pattern
    used by the winning system at the TSAR 2025 Shared Task on
    Readability-Controlled Text Simplification.

    This pipeline uses a 4-level readability scale (1 = simplest, 4 =
    hardest; BAREC's original, harder level 5 is excluded from this
    pipeline entirely -- this is not BAREC's native 19-level scale). Target
    level 1 or 2: short, direct sentences using common, everyday vocabulary
    that a general adult reader, or an upper-elementary-school reader,
    could understand on a single read. As a rough length anchor from this
    pipeline's own corpus statistics, level-1 sentences average about 5
    words and level-2 about 12 -- but word choice, morphology, and content
    matter as much as length, so do not simplify by truncation alone.

    Favor high-frequency words over rare or classical/literary vocabulary.
    Split long or compound sentences into shorter ones where that helps.
    Reduce unnecessary subordinate clauses.

    Morphological complexity, specifically: across every study we have on
    Arabic reading difficulty in dyslexic readers (a developmental study
    spanning grades 3, 6, 9, and 12; a 16-study review), morphological
    complexity predicts reading difficulty more strongly than phonology or
    vowelization -- this is not a minor style point, it is the single
    biggest lever available. Four concrete, checkable things to act on:
    (1) Do not stack more than two attached prefixes/suffixes on one word
    (conjunctions, prepositions, the definite article, and attached
    pronouns all count) -- split into separate words instead of a longer
    chain. (2) When a genuinely simpler synonym exists, prefer an
    unaugmented (Form I) verb or noun over one built from a derived
    pattern (Form II-X and their derivatives, e.g. مفتاح-style instrument
    nouns or استفعل-pattern verbs) -- derived forms are longer and carry
    more processing load. (3) Where a sound plural (-ون/-ين/-ات) is a
    natural alternative, prefer it over a broken/irregular plural -- but
    many common nouns have no sound-plural form, so do not force an
    unnatural one. (4) Between two equally simple, equally common
    synonyms, prefer the one whose root letters stay visually intact over
    one where a root letter is dropped, mutated, or merged into a shadda
    -- but never trade away a common, high-frequency word for a rarer one
    just to satisfy this; most basic Arabic vocabulary (قال, جاء, كان)
    already has a mutated root, so this is a tie-breaker between otherwise
    equal choices, not a reason to avoid ordinary words.

    Dyslexia-specific style, beyond general simplicity: state the literal
    meaning directly rather than a metaphor, idiom, or other figurative
    expression -- rewording a figure of speech into its plain sense is a
    valid simplification, not a change of meaning, as long as the
    underlying claim survives. Prefer active voice over passive voice
    where the choice does not affect meaning. Avoid double negatives or
    stacked negation. If splitting a sentence in two would leave a later
    part's pronoun referring back unclearly, repeat the noun instead of
    using the pronoun.

    Do not add, remove, or alter any fact, entity, number, name, date, or
    claim from the source sentence. Do not add explanations, examples, or
    commentary that were not in the source. Do not soften, strengthen, or
    otherwise shift the original meaning. Preserve negation exactly. If a
    technical or proper term cannot be simplified without changing its
    meaning, keep the term as-is rather than inventing an inaccurate
    substitute.

    Output grammatically correct Modern Standard Arabic only -- no dialect,
    no other language, no transliteration. Write no diacritics (tashkeel)
    and no tatweel.

    Keep the source's form -- these are checked automatically, and a
    candidate that breaks one is thrown away:
    (1) Quiz and multiple-choice items: simplify the question stem and the
    wording inside each option, but keep every option label -- (أ), (ب),
    (ج), (د) -- in the same order, each followed by its own option. Never
    merge the options into one sentence, never drop or add an option, and
    never state an option as a fact. A true/false item stays a statement
    to be judged: do not answer it, and do not reword it so the answer
    shows.
    (2) Copy any quoted Quran verse or hadith text word for word.
    (3) Keep every religious honorific exactly where the source has it:
    صلى الله عليه وسلم، عليه السلام، رضي الله عنه / عنها / عنهم، كرم الله
    وجهه، عز وجل، سبحانه وتعالى، جل جلاله. Keep people's full names.
    (4) The source may be a cut piece of a longer sentence -- ending with
    «،» or «؛» or «:» or with no mark at all. Then the rewrite is the same
    piece: end it the same way, and do not add words to finish the
    thought.

    Make the candidates genuinely different from each other -- vary word
    choice, sentence order, and how (or whether) the sentence is split into
    more than one -- not near-duplicates that differ only in punctuation or
    a single synonym swap. Different candidates are only useful for
    reranking if they actually represent different simplification attempts.
    """

    original_text: str = dspy.InputField(
        desc="A Modern Standard Arabic sentence (or a cut piece of one, or a quiz item) at level 3 or 4 "
        "of this pipeline's 4-level scale."
    )
    simplified_candidates: list[str] = dspy.OutputField(
        desc=f"Exactly {NUM_CANDIDATES} different candidate rewrites of original_text, each one "
        "independently rewritten to level 1 or 2 of this pipeline's 4-level scale, each preserving "
        "the original's meaning exactly. The candidates must be meaningfully different from each "
        "other, not trivial variants."
    )


STRONG_SIMPLIFICATION = """
Simplify hard -- a light touch is not enough. Every rewrite must read at least two full grade levels
easier than the source. Concretely, in every candidate:
- Keep each sentence to about 10 words or fewer. Split any longer sentence into several short ones, each
  stating one fact, and repeat the noun instead of a pronoun where needed.
- Replace every formal, rare, literary or technical word that has an everyday equivalent with the most
  common word a 10-year-old would know. Keep a term only when no common word says the same thing.
- Remove relative clauses (الذي، التي، الذين), participle phrases and nominalizations; use a short verb
  sentence instead (write "بدأ الناس يستعملون" rather than "بدأ استعمال").
- At most one attached prefix or suffix per word where a separate word can carry it.
All of the rules above still hold: no fact, name, number or negation may be added, dropped or changed,
and every quiz option, verse and honorific stays as required."""

SimplifyToEasyArabicStrong = SimplifyToEasyArabic.with_instructions(
    SimplifyToEasyArabic.instructions + "\n" + STRONG_SIMPLIFICATION
)

# Targets the meaning errors an audit of 1,156 accepted pairs found: most came from the generator misreading
# the source the same way in every candidate -- a qualifier's scope lost, "voluntary" turned into "must", the
# speaker or the agent swapped, a hedge or quantifier dropped, a legal idiom misread.
FAITHFUL_SIMPLIFICATION = """
Before writing any candidate, read the source for these and keep every one of them, with the same meaning,
in every candidate:
- Who does what to whom: the agent, the action and the one it is done to. In dialogue, who is speaking
  and to whom. Never swap them, and never turn "X caused Y" into "Y caused X".
- Modality and force: must / may / should / voluntary / forbidden / "under penalty of", possibility vs
  certainty, a claim vs an allegation vs a fact. Never make a statement stronger or weaker.
- Scope: a qualifier such as "on religious or tribal grounds", "in Jordan" or "public" limits whatever it
  attaches to; when you split a sentence, repeat it wherever it applies so no sentence claims more than
  the source.
- Hedges and quantifiers: about, at least, only, most, some, often, usually, may, perhaps (حوالي، نحو،
  على الأقل، فقط، معظم، بعض، غالبا، عادة، قد، ربما). Keep each one.
- Numbers, dates, names, titles and technical or legal terms exactly as given.
If a phrase is an idiom, a fixed legal formula or unclear, keep its wording rather than guess its meaning."""

SimplifyToEasyArabicStrict = SimplifyToEasyArabic.with_instructions(
    SimplifyToEasyArabic.instructions + "\n" + STRONG_SIMPLIFICATION + "\n" + FAITHFUL_SIMPLIFICATION
)
GENERATOR_SIGNATURES = {
    "base": SimplifyToEasyArabic, "strong": SimplifyToEasyArabicStrong, "strict": SimplifyToEasyArabicStrict,
}


class CheckSemanticEquivalence(dspy.Signature):
    """Score how completely EACH of several candidate simplifications preserves
    the exact meaning of the same original Arabic sentence, on a continuous
    0.0-1.0 scale per candidate -- not a boolean, and not just one candidate
    at a time. Scoring all of NUM_CANDIDATES candidates from the same original
    in a single pass (instead of one call per candidate) is far cheaper and
    just as valid, since each candidate is judged independently against the
    one fixed original -- but it means you must judge each candidate entirely
    on its own merits: do not let your verdict on one candidate anchor,
    average with, or otherwise influence your verdict on another. A candidate
    that changes the meaning is wrong regardless of how the other candidates
    from the same batch scored.

    A degree-of-drift score is more useful than a pass/fail verdict: it lets
    downstream code rank multiple candidate simplifications against each
    other, and lets the pass/fail threshold be tuned later without
    retraining this judge.

    For EACH candidate, compare it against original_text on:
    (1) every factual claim, entity, name, number, date, and relationship in
        the original is still present and unchanged in the candidate;
    (2) nothing has been added to the candidate that was not present or
        directly implied in the original;
    (3) the candidate does not contradict, soften, strengthen, or reverse
        any part of the original's meaning;
    (4) negation is preserved exactly -- a dropped or added negative is a
        meaning change, never "just" a simplification.

    A candidate can be heavily reworded, shortened, split into more than one
    sentence, or use much simpler vocabulary and still score near 1.0 --
    style, length, and vocabulary changes are expected and desired, and must
    not by themselves lower the score. Only real meaning drift should pull
    the score down.

    Use the full range, not just the extremes:
    - 1.0: no detectable meaning change at all.
    - 0.7-0.9: essentially equivalent -- at most a very minor nuance or
      emphasis shift that doesn't change what's actually being claimed.
    - 0.4-0.6: partially equivalent -- some real information was added,
      dropped, or softened/strengthened, but the core gist survives.
    - 0.0-0.3: the meaning was substantially changed, reversed, or a central
      fact/entity/negation was altered or lost.
    """

    original_text: str = dspy.InputField(desc="The original Arabic sentence.")
    simplified_candidates: list[str] = dspy.InputField(
        desc="Candidate simplified versions of original_text, each to be scored independently."
    )
    reasoning_per_candidate: list[str] = dspy.OutputField(
        desc="One short reasoning string per candidate, in the SAME ORDER as simplified_candidates "
        "(same list length) -- for each candidate, state concretely what (if anything) changed in "
        "meaning versus original_text. Judge each candidate independently; do not compare candidates "
        "to each other, only each one to original_text."
    )
    equivalence_scores: list[float] = dspy.OutputField(
        desc="One score per candidate, in the SAME ORDER as simplified_candidates and "
        "reasoning_per_candidate (all three lists must be the same length). Each score is a number "
        "from 0.0 to 1.0 (1.0 = fully equivalent, 0.0 = meaning completely changed). Use fine-grained "
        "values across the whole range, not just 0.0/0.5/1.0."
    )


class ClassifyReadabilityLevel(dspy.Signature):
    """Classify an Arabic sentence into one of this pipeline's 4 readability
    levels (1 = simplest, 4 = hardest). This is a 4-level scale specific to
    this pipeline, not BAREC's native 19-level scale -- levels here are
    coarser bands, and BAREC's original level 5 (hardest) is excluded from
    this pipeline entirely.

    Base the judgment on BAREC's own six annotation dimensions, and on
    whichever is the sentence's single hardest feature -- a sentence is
    only as easy as its hardest phenomenon, not its average:
    - Spelling: short, common word forms vs. long or rare ones.
    - Word count: few distinct/unique words vs. many.
    - Morphology: simple word forms vs. complex clitic stacking (multiple
      attached prefixes/suffixes on one word) or irregular/dual inflection.
    - Syntax: simple, direct sentence structure vs. compound or subordinate
      clauses, passive voice, or unusual word order.
    - Vocabulary: common, everyday words vs. technical, classical, or
      literary vocabulary.
    - Content: no specialized prior knowledge needed vs. requiring
      domain-specific or abstract background knowledge.

    Rough length anchors from this pipeline's own corpus (word count alone
    does not decide the level -- one rare word or one complex construction
    can outweigh a short sentence): level 1 averages about 5 words, level 2
    about 12, level 3 about 18, level 4 about 25.
    """

    text: str = dspy.InputField(desc="A single Arabic sentence to classify.")
    level: int = dspy.OutputField(
        desc="An integer from 1 to 4 (1 = simplest, 4 = hardest) on this pipeline's 4-level scale."
    )


# --------------------------------------------------------------------------------------
# DSPy wiring
# --------------------------------------------------------------------------------------


def raise_fd_limit() -> None:
    """litellm leaks roughly one socket per call under a thread pool; at the usual soft limit of 1024 open
    files a long run starts failing every call with "Too many open files" after ~2k calls. Raise the soft
    limit to the hard limit (which varies by host; asking for more than it fails)."""
    import resource
    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    resource.setrlimit(resource.RLIMIT_NOFILE, (hard, hard))
    print(f"open-file limit raised {soft} -> {hard}")


def _vllm_lm(model: str, api_base: str, temperature: float, max_tokens: int) -> dspy.LM:
    # enable_thinking=False: both Gemma 4 and Qwen3.8 think by default, which spends the token budget
    # before the structured fields DSPy parses (the same failure DeepSeek's thinking mode caused).
    # timeout=300: a busy local server queues requests instead of rejecting them.
    return dspy.LM(
        f"openai/{model}", api_base=api_base, api_key="local", temperature=temperature, max_tokens=max_tokens,
        timeout=300, num_retries=2, extra_body={"chat_template_kwargs": {"enable_thinking": False}},
    )


def configure_dspy(
    backend: str = "deepseek",
    generator_url: str | None = None,
    judge_url: str | None = None,
    generator_model: str = VLLM_GENERATOR_MODEL,
    judge_model: str = VLLM_JUDGE_MODEL,
    prompt: str = "base",
) -> tuple[dspy.Module, dspy.Module, CamelReadability, LexicalScorer]:
    """Build the generator, the equivalence validator, the local CAMeL readability model, and the
    local lexical-difficulty scorer (AoA + word length).

    backend "vllm": generator and judge are self-hosted OpenAI-compatible servers (generator_url,
    judge_url). The generator is a plain dspy.Predict there, not ChainOfThought -- its separate
    reasoning field roughly doubles the generated tokens, which is the dominant GPU cost, and the
    docstring already carries the guidance that field was for.

    Generation gets a higher temperature (varied phrasing is fine, even
    desirable, and NUM_CANDIDATES candidates in one call need genuine
    variety to be worth reranking); the equivalence judge gets temperature 0
    (consistent verdicts matter more than varied ones for a judge). Readability
    and lexical-difficulty scoring never go through an LLM call at pipeline runtime -- see
    COMPILED_LEVEL_CLASSIFIER_PATH's comment for why the local CAMeL model replaced readability's
    LLM call, and lexical_scorer.py's own docstring for the (offline, one-time) LLM AoA ratings
    LexicalScorer loads from disk here rather than calling anything live.
    """
    # Import litellm fully here, on one thread: dspy imports it lazily on the first call, and with a thread
    # pool that first call happens on dozens of threads at once, which fails every one of them with
    # "partially initialized module 'litellm' has no attribute 'completion'".
    import litellm
    litellm.completion  # noqa: B018
    raise_fd_limit()
    if backend == "vllm":
        global GENERATOR_MODEL_ID, JUDGE_MODEL_ID
        GENERATOR_MODEL_ID, JUDGE_MODEL_ID = generator_model, judge_model
        generation_lm = _vllm_lm(generator_model, generator_url, temperature=0.7, max_tokens=2048)
        judge_lm = _vllm_lm(judge_model, judge_url, temperature=0.0, max_tokens=2048)
        dspy.configure(lm=generation_lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))
        generator = dspy.Predict(GENERATOR_SIGNATURES[prompt])
        generator.set_lm(generation_lm)
        global PROMPT_VARIANT
        PROMPT_VARIANT = prompt
        equivalence_validator = dspy.Predict(CheckSemanticEquivalence)
        if COMPILED_EQUIVALENCE_VALIDATOR_PATH.exists():
            equivalence_validator.load(str(COMPILED_EQUIVALENCE_VALIDATOR_PATH))
        equivalence_validator.set_lm(judge_lm)
        return generator, equivalence_validator, load_readability_classifier(), LexicalScorer()

    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and "
            "fill it in, or export it directly, e.g.:\n  export DEEPSEEK_API_KEY=sk-...\n"
            "(--dry-run doesn't need it.)"
        )

    # thinking={"type": "disabled"}: DeepSeek V4.1 Flash defaults to an internal "thinking" pass
    # (a separate reasoning_content field) that, left on, consumes the max_tokens budget before the
    # model writes the actual structured answer DSPy needs. Disabling it is what our own
    # dspy.ChainOfThought "reasoning" field is already for; the two compete for the same budget.
    # timeout=90: without this, a stalled connection hangs indefinitely instead of failing -- a
    # failure gets caught and skipped by run_hard_pipeline's try/except, a hang blocks the run.
    common_kwargs = dict(api_key=api_key, thinking={"type": "disabled"}, timeout=90)
    # Both budgets have real headroom above the minimum that works: NUM_CANDIDATES=5 candidates
    # (generation) and 5 reasoning strings + 5 scores (judging) in one batched call have enough
    # length variance that a tighter budget risks the reasoning field eating the whole allowance
    # before any candidate/score gets written, silently truncating the response.
    generation_lm = dspy.LM(DEEPSEEK_MODEL, temperature=0.7, max_tokens=4096, **common_kwargs)
    judge_lm = dspy.LM(DEEPSEEK_MODEL, temperature=0.0, max_tokens=8192, **common_kwargs)
    # use_json_adapter_fallback=False: DSPy's default behavior retries a parse failure via a
    # JSON-mode adapter, which sends a `response_format` param DeepSeek's endpoint rejects --
    # turning a single truncated/malformed response into a fatal crash instead of a recoverable
    # one. Plain ChatAdapter parses our fields fine on its own.
    dspy.configure(lm=generation_lm, adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))

    generator = dspy.ChainOfThought(SimplifyToEasyArabic)
    generator.set_lm(generation_lm)

    # dspy.Predict, not ChainOfThought: CheckSemanticEquivalence now declares its own
    # reasoning_per_candidate output field explicitly (ordered before equivalence_scores, so the
    # model still reasons before scoring, same benefit ChainOfThought would give) -- wrapping it
    # in ChainOfThought too would add a second, redundant top-level "reasoning" field on top of
    # the one we already asked for, wasting output tokens on the same thing twice.
    equivalence_validator = dspy.Predict(CheckSemanticEquivalence)
    if COMPILED_EQUIVALENCE_VALIDATOR_PATH.exists():
        equivalence_validator.load(str(COMPILED_EQUIVALENCE_VALIDATOR_PATH))
        print(f"loaded optimized equivalence validator from {COMPILED_EQUIVALENCE_VALIDATOR_PATH}")
    else:
        print(
            f"no compiled equivalence validator at {COMPILED_EQUIVALENCE_VALIDATOR_PATH} -- using "
            "it zero-shot. Run optimize_equivalence_validator.py first to calibrate it against "
            "human-annotated ground truth."
        )
    equivalence_validator.set_lm(judge_lm)

    readability = load_readability_classifier()
    lexical_scorer = LexicalScorer()

    return generator, equivalence_validator, readability, lexical_scorer


def hardest_sentence_leads(readability: CamelReadability, original_text: str, candidates: list[str]) -> list[float]:
    """Per candidate: CAMeL expected level of the source (scored whole -- it is one BAREC sentence; MCQs on
    the stem) minus the level of the candidate's HARDEST sentence. CAMeL is a sentence-level model: scoring
    a multi-sentence rewrite as one text reads short sentences as one long one and hides the gain from
    splitting, while the hardest sentence keeps one hard sentence from hiding behind easy ones."""
    units = [readability_units(c) for c in candidates]
    texts = list(dict.fromkeys([mcq_stem(original_text)] + [u for us in units for u in us]))
    level = dict(zip(texts, readability.expected_level(readability.predict_probs(texts))))
    src = float(level[mcq_stem(original_text)])
    return [src - max(float(level[u]) for u in us) for us in units]


def simplify_and_validate(
    generator: dspy.Module,
    equivalence_validator: dspy.Module,
    readability: CamelReadability,
    lexical_scorer: LexicalScorer,
    original_text: str,
) -> dict:
    """Generate NUM_CANDIDATES simplifications in ONE call, score all of them for equivalence in
    ONE call, score their readability locally (free, no API call; each candidate's P(easy) against
    the original's) and their lexical difficulty locally too (free; AoA + word length via
    LexicalScorer), and keep the best-scoring one -- 2 API calls per hard sentence total, not
    NUM_CANDIDATES*3 (see NUM_CANDIDATES's own comment for the TSAR 2025/EhiMeNLP precedent behind
    generating multiple candidates and reranking).

    Every candidate is first normalized to what would ship (corpus_constraints.normalize_candidate:
    no tashkeel, the source's own ending mark) and checked against the deterministic structure gates
    (MCQ option labels, honorifics, quoted verses). Only candidates passing those are sent to the
    judge -- a structurally broken candidate is never eligible, so judging it would only spend tokens.

    Eligible (`passed`) = equivalence_score >= EQUIVALENCE_THRESHOLD AND readability_lead >=
    MIN_READABILITY_LEAD (CAMeL's expected 19-level readability dropped by at least that many levels). Among eligible candidates the winner is chosen by
    (equivalence_score >= TIER_A_EQ_THRESHOLD, readability_lead, equivalence_score): a confidently
    faithful rewrite always beats a merely acceptable one, and within that tier the largest readability
    gain wins. The objective is the biggest faithful readability gain, not moving a sentence into the
    easy band, so the P(easy) rise (d_logit) is logged but no longer gates. If nothing is eligible the
    most faithful candidate is still returned (tier C, never shipped) so the record stays auditable.

    Defensive against list-length mismatches: batched list outputs are a real new failure mode a
    single-field output never had (the model can under/over-generate items, or the three lists
    -- candidates, scores, reasoning -- can come back different lengths). We use only the
    shortest common length across whatever came back rather than assuming NUM_CANDIDATES items
    are always present, and raise if that leaves nothing scorable at all (caught by
    run_hard_pipeline's existing per-sentence try/except, same as any other failure).
    """
    gen_out = generator(original_text=original_text)
    raw_candidates = [str(c) for c in list(gen_out.simplified_candidates)[:NUM_CANDIDATES]]
    if not raw_candidates:
        raise ValueError("generator returned zero candidates")
    normalized = list(dict.fromkeys(t for t in (normalize_candidate(original_text, c) for c in raw_candidates) if t))
    gate_results = {t: structure_gates(original_text, t) for t in normalized}
    candidate_texts = [t for t in normalized if all(gate_results[t].values())]
    rejected_by_gates = [{"simplified_text": t, **gate_results[t]} for t in normalized if not all(gate_results[t].values())]
    # Readability is local and nearly free, the judge is the expensive call: a candidate below
    # MIN_READABILITY_LEAD can never be eligible, so it is scored here and never sent to the judge.
    below_lead, sentence_lead = [], {}
    if candidate_texts:
        leads = hardest_sentence_leads(readability, original_text, candidate_texts)
        sentence_lead = dict(zip(candidate_texts, leads))
        below_lead = [{"simplified_text": t, "readability_lead": l}
                      for t, l in zip(candidate_texts, leads) if l < MIN_READABILITY_LEAD]
        candidate_texts = [t for t, l in zip(candidate_texts, leads) if l >= MIN_READABILITY_LEAD]
    if not candidate_texts:
        best_below = max(below_lead, key=lambda c: c["readability_lead"], default=None)
        return {
            "original_text": original_text,
            "simplified_text": best_below["simplified_text"] if best_below else (normalized or raw_candidates)[0],
            "equivalence_score": 0.0, "equivalent": False,
            "equivalence_reasoning": "not judged: no candidate passed the structure gates and the readability-lead floor",
            "readability_lead": best_below["readability_lead"] if best_below else 0.0,
            "readability_passed": False, "passed": False, "acceptance_tier": "C",
            "num_candidates": 0, "num_passed": 0, "n_candidates_generated": len(raw_candidates),
            "n_rejected_by_gates": len(rejected_by_gates), "rejected_by_gates": rejected_by_gates,
            "n_below_lead": len(below_lead), "below_lead": below_lead,
            "all_candidates": [], "equivalence_threshold": EQUIVALENCE_THRESHOLD,
            "min_readability_lead": MIN_READABILITY_LEAD, "tier_a_eq_threshold": TIER_A_EQ_THRESHOLD,
            "selection_rule": SELECTION_RULE, "generator_model": GENERATOR_MODEL_ID, "judge_model": JUDGE_MODEL_ID,
            "prompt_variant": PROMPT_VARIANT,
        }

    eq_out = equivalence_validator(original_text=original_text, simplified_candidates=candidate_texts)
    scores = list(eq_out.equivalence_scores)
    reasons = list(eq_out.reasoning_per_candidate)

    n_generated = len(candidate_texts)
    n = min(n_generated, len(scores), len(reasons))  # shortest common length -- see docstring
    if n == 0:
        raise ValueError(
            f"equivalence validator returned mismatched/empty lists: "
            f"{n_generated} candidates, {len(scores)} scores, {len(reasons)} reasons"
        )
    list_mismatch = n < n_generated
    if list_mismatch:
        # min() truncates the TAIL of candidate_texts, so if the judge returns fewer items than it
        # was sent, the dropped candidates are always the LAST ones, not a random subset -- a
        # positional selection bias worth logging rather than assuming benign.
        print(
            f"  WARNING: equivalence validator list mismatch -- sent {n_generated} candidates, "
            f"got {len(scores)} scores / {len(reasons)} reasons; keeping the first {n} "
            f"(candidates at positions {n}..{n_generated - 1} silently dropped)."
        )
    candidate_texts, scores, reasons = candidate_texts[:n], scores[:n], reasons[:n]

    # Local and free: every text is scored on its own, and each candidate is compared with the original.
    r = score_readability(readability, [original_text] * n, candidate_texts)

    original_word_count = len(TOKEN.findall(original_text)) or 1  # denominator for length_ratio below

    candidates = []
    for i, (text, raw_score, reasoning) in enumerate(zip(candidate_texts, scores, reasons)):
        equivalence_score = max(0.0, min(1.0, float(raw_score)))  # clamp against a judge that
        # ignores the 0.0-1.0 instruction and returns something out of range
        equivalent = equivalence_score >= EQUIVALENCE_THRESHOLD
        predicted_level = int(r["predicted_level"][i])
        d_logit = float(r["d_logit"][i])
        readability_passed = sentence_lead[text] >= MIN_READABILITY_LEAD
        mean_aoa, mean_zipf, _ = lexical_scorer.text(text)
        # DIAC.sub: strip diacritics/tatweel before measuring length -- TOKEN's character class
        # includes them (so a diacritized word stays one token, correctly), but counting them
        # toward len() overstates how long the word actually reads, confirmed against a real
        # batch: 153/482 texts carried diacritics, inflating mean_word_len from 3.93 to 4.65.
        words = [DIAC.sub("", w) for w in TOKEN.findall(text)]
        mean_word_len = float(np.mean([len(w) for w in words])) if words else 0.0
        word_count = len(words)
        length_ratio = word_count / original_word_count  # this candidate's word count vs the
        # original's -- an audit/diagnostic field (expansion vs. truncation), not currently an
        # input to ease_score itself.
        # p_easy_simplified is THIS candidate's own absolute P(easy) (not the pair-delta d_logit
        # above) -- the SAMER fit used each text's own logit(P(easy)), not a delta, since reranking
        # compares candidates against each other, not against the original.
        p_easy_clip = min(max(float(r["p_easy_simplified"][i]), 1e-6), 1 - 1e-6)
        camel_logit = float(np.log(p_easy_clip / (1 - p_easy_clip)))
        # mean_word_len is still computed and logged (below, and in all_candidates) as a diagnostic
        # field -- it just isn't in the formula itself, see EASE_W_CAMEL_LOGIT's comment for why.
        ease_score = EASE_W_CAMEL_LOGIT * camel_logit + EASE_W_MEAN_AOA * mean_aoa + EASE_INTERCEPT
        # readability_lead: how hard the original was and how many (continuous, native 19-level)
        # levels it moved -- see CamelReadability.expected_level's docstring. A per-candidate field
        # like ease_score/d_logit, not a formula input; meant for post-hoc reporting on the accepted
        # (tier A/B) pairs, e.g. "average lead by source level", not for gating or reranking.
        expected_level_original = float(r["expected_level_original"][i])
        expected_level_simplified = float(r["expected_level_simplified"][i])
        readability_lead = sentence_lead[text]  # hardest-sentence lead: the gate and the ranking key
        readability_lead_whole = float(r["readability_lead"][i])  # the rewrite scored as one text, reference only
        candidates.append(
            {
                "simplified_text": text,
                "equivalence_score": equivalence_score,
                "equivalent": equivalent,
                "equivalence_reasoning": str(reasoning),
                "predicted_level": predicted_level,
                "is_easy": predicted_level <= EASY_LEVEL_CEILING,
                "expected_level_original": expected_level_original,
                "expected_level_simplified": expected_level_simplified,
                "readability_lead": readability_lead,
                "readability_lead_whole": readability_lead_whole,
                "p_easy_original": float(r["p_easy_original"][i]),
                "p_easy_simplified": float(r["p_easy_simplified"][i]),
                "d_logit": d_logit,
                "readability_passed": readability_passed,
                "passed": equivalent and readability_passed,
                "acceptance_tier": acceptance_tier(equivalent, readability_passed, equivalence_score),
                "mean_aoa": mean_aoa,
                "mean_zipf": mean_zipf,
                "mean_word_len": mean_word_len,
                "word_count": word_count,
                "char_count": len(text),
                "length_ratio": length_ratio,
                "camel_logit": camel_logit,
                "ease_score": ease_score,
            }
        )

    def rank(c: dict) -> tuple:  # SELECTION_RULE; see the docstring
        if c["passed"]:
            return (1, c["equivalence_score"] >= TIER_A_EQ_THRESHOLD, c["readability_lead"], c["equivalence_score"])
        return (0, False, 0.0, c["equivalence_score"])

    winner_index = max(range(len(candidates)), key=lambda idx: rank(candidates[idx]))
    best = candidates[winner_index]
    num_passed = sum(1 for c in candidates if c["passed"])

    return {
        "original_text": original_text,
        "simplified_text": best["simplified_text"],
        "equivalence_score": best["equivalence_score"],
        "equivalent": best["equivalent"],
        "equivalence_reasoning": best["equivalence_reasoning"],
        "predicted_level": best["predicted_level"],
        "is_easy": best["is_easy"],
        "p_easy_original": best["p_easy_original"],
        "p_easy_simplified": best["p_easy_simplified"],
        "d_logit": best["d_logit"],
        "readability_passed": best["readability_passed"],
        "passed": best["passed"],
        "acceptance_tier": best["acceptance_tier"],
        "expected_level_original": best["expected_level_original"],
        "expected_level_simplified": best["expected_level_simplified"],
        "readability_lead": best["readability_lead"],
        "mean_aoa": best["mean_aoa"],
        "mean_zipf": best["mean_zipf"],
        "mean_word_len": best["mean_word_len"],
        "ease_score": best["ease_score"],
        "num_candidates": len(candidates),
        "num_passed": num_passed,
        "n_candidates_generated": len(raw_candidates),
        "n_rejected_by_gates": len(rejected_by_gates),
        "rejected_by_gates": rejected_by_gates,
        "n_below_lead": len(below_lead),
        "below_lead": below_lead,
        "min_readability_lead": MIN_READABILITY_LEAD,
        "list_mismatch": list_mismatch,
        # Full record (all candidates, not just the winner) plus the selection index and the
        # threshold/formula versions in force -- makes the accept/reject decision replayable and
        # auditable against every candidate, not just whichever one won.
        "winner_index": winner_index,
        "all_candidates": candidates,
        "equivalence_threshold": EQUIVALENCE_THRESHOLD,
        "readability_tau": TAU,
        "tier_a_eq_threshold": TIER_A_EQ_THRESHOLD,
        "ease_formula_version": EASE_FORMULA_VERSION,
        "selection_rule": SELECTION_RULE,
        "prompt_variant": PROMPT_VARIANT,
        "generator_model": GENERATOR_MODEL_ID,
        "judge_model": JUDGE_MODEL_ID,
    }


def load_checkpoint() -> list[dict]:
    if not HARD_CHECKPOINT_PATH.exists():
        return []
    rows = []
    with open(HARD_CHECKPOINT_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    if rows and "readability_passed" not in rows[0]:
        raise SystemExit(
            f"{HARD_CHECKPOINT_PATH} was written before the CAMeL readability gate (#17), so resuming it would mix two "
            "accept criteria. Move it aside (or pass a fresh run) and start again."
        )
    return rows


def _process_row(
    row: dict,
    generator: dspy.Module,
    equivalence_validator: dspy.Module,
    readability: CamelReadability,
    lexical_scorer: LexicalScorer,
) -> tuple[dict, dict | None, Exception | None]:
    """One source's worth of work, factored out so it can run on any thread: the DeepSeek calls
    (generation + judging) dominate the wall time and are I/O-bound (network round trips), so
    ThreadPoolExecutor gets real concurrency despite the GIL. The local CAMeL scoring inside
    simplify_and_validate is a single shared onnxruntime.InferenceSession, which is documented
    safe for concurrent run() calls from multiple threads -- no per-thread model copy needed."""
    try:
        result = simplify_and_validate(generator, equivalence_validator, readability, lexical_scorer, row["Sentence"])
    except Exception as e:
        return row, None, e
    result["ID"] = row["ID"]
    result["source_level"] = row["Readability_Level_5"]
    result["source_level_19"] = row["Readability_Level_19"]  # gold, not predicted -- see KEEP_COLS
    for col in ("Source", "Domain", "barec_split"):
        result[col] = row[col]
    return row, result, None


def run_hard_pipeline(
    hard_sample: pl.DataFrame,
    generator: dspy.Module,
    equivalence_validator: dspy.Module,
    readability: CamelReadability,
    lexical_scorer: LexicalScorer,
    concurrency: int = 1,
    max_consecutive_failures: int = 400,
) -> pl.DataFrame:
    HARD_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)

    done = load_checkpoint()
    done_ids = {row["ID"] for row in done}
    if done_ids:
        print(f"resuming: {len(done_ids)} hard sentences already completed in a prior run "
              f"(from {HARD_CHECKPOINT_PATH})")

    remaining = hard_sample.filter(~pl.col("ID").is_in(done_ids))

    failures = 0
    # consecutive_failures resets to 0 on every successful write -- it tracks a *sustained* failure
    # streak (e.g. the account's API balance hitting zero, where every subsequent call fails but is
    # still caught and logged below rather than crashing), not the overall failure count. Without
    # this, a run whose funding runs out mid-flight would grind for hours logging nothing but skips.
    consecutive_failures = 0
    stopped_early = False
    write_lock = threading.Lock()
    with open(HARD_CHECKPOINT_PATH, "a", encoding="utf-8") as f:
        def _write(result: dict) -> None:
            with write_lock:
                f.write(json.dumps(result, ensure_ascii=False) + "\n")
                f.flush()
                os.fsync(f.fileno())

        rows = list(remaining.iter_rows(named=True))
        if concurrency <= 1:
            for row in tqdm(rows, total=len(rows), desc="hard band"):
                row, result, err = _process_row(row, generator, equivalence_validator, readability, lexical_scorer)
                if err is not None:
                    # A single truncated/malformed LM response (or a stalled connection after the
                    # machine slept) shouldn't kill a run that's already spent real API calls on
                    # everything before it -- log and move on.
                    failures += 1
                    consecutive_failures += 1
                    tqdm.write(f"  skipped ID {row['ID']}: {type(err).__name__}: {str(err)[:150]}")
                    if consecutive_failures >= max_consecutive_failures:
                        tqdm.write(f"  STOPPING: {consecutive_failures} consecutive failures with no successes "
                                   f"in between (>= max_consecutive_failures={max_consecutive_failures}) -- likely a "
                                   "systemic issue (exhausted API balance, an outage), not isolated bad responses. "
                                   "Already-written results are safely on disk; rerun to resume.")
                        stopped_early = True
                        break
                    continue
                consecutive_failures = 0
                _write(result)
        else:
            # Concurrent path: each source's 2 DeepSeek calls are independent network round trips,
            # so a thread pool cuts wall time roughly in proportion to concurrency instead of
            # serializing every request behind the last one's latency. Submit everything up front
            # (bounded by ThreadPoolExecutor's own queueing) and drain via as_completed so results
            # land on disk as soon as each source finishes, not in submission order.
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futures = {
                    pool.submit(_process_row, row, generator, equivalence_validator, readability, lexical_scorer): row
                    for row in rows
                }
                for future in tqdm(as_completed(futures), total=len(futures), desc=f"hard band (x{concurrency} concurrent)"):
                    row, result, err = future.result()
                    if err is not None:
                        failures += 1
                        consecutive_failures += 1
                        tqdm.write(f"  skipped ID {row['ID']}: {type(err).__name__}: {str(err)[:150]}")
                        if consecutive_failures >= max_consecutive_failures:
                            tqdm.write(f"  STOPPING: {consecutive_failures} consecutive failures with no successes "
                                       f"in between (>= max_consecutive_failures={max_consecutive_failures}) -- "
                                       "cancelling every not-yet-started source. Already-written results are "
                                       "safely on disk; rerun to resume.")
                            stopped_early = True
                            # Cancel every future that hasn't started yet -- with concurrency workers
                            # already all rows are submitted up front, so without this the pool would
                            # keep draining its whole backlog (each failing the same way) instead of
                            # actually stopping.
                            for f_ in futures:
                                f_.cancel()
                            break
                        continue
                    consecutive_failures = 0
                    _write(result)

    if stopped_early:
        print(f"stopped early after {failures} total failures ({consecutive_failures} consecutive) -- "
              f"{len(rows) - failures} of {len(rows)} sources in this run attempted before stopping.")
    if failures:
        print(f"{failures} / {remaining.shape[0]} hard sentences failed and were skipped this run")

    checkpoint_rows = load_checkpoint()
    if not checkpoint_rows:
        # Every attempt failed (or this is a fresh run with nothing to resume) -- pl.DataFrame([])
        # has no columns at all, so filtering on "ID" below would crash with ColumnNotFoundError
        # rather than reporting "0 succeeded" cleanly.
        print("WARNING: no hard-band results at all (every attempt failed, or nothing has run yet).")
        return pl.DataFrame(schema={"ID": pl.Int64, "passed": pl.Boolean, "equivalent": pl.Boolean, "readability_passed": pl.Boolean})
    # Scalar summary columns only: the nested candidate records vary in shape between rows (a source whose
    # candidates all failed the structure gates has none), which polars can't infer as one schema.
    summary_cols = ("ID", "passed", "equivalent", "readability_passed", "acceptance_tier", "equivalence_score",
                    "readability_lead", "num_passed", "n_rejected_by_gates")
    all_done = pl.DataFrame([{k: r.get(k) for k in summary_cols} for r in checkpoint_rows], infer_schema_length=None)
    # Guard against a stale checkpoint from a run with a different selection: only this run's sources.
    return all_done.filter(pl.col("ID").is_in(hard_sample["ID"]))


# --------------------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--sample-fraction", type=float, default=0.02, help="Stratified sample fraction (default: 0.02).")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed (default: 42).")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load, clean, and sample only -- print counts and stop before any LM call.",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help="Number of hard-band sources to process concurrently via a thread pool (default: 1, "
        "sequential -- the original behavior). The per-source work is dominated by 2 network-bound "
        "DeepSeek calls, so this is I/O concurrency, not CPU parallelism; 20-30 is a reasonable "
        "starting point before hitting DeepSeek's own rate limits.",
    )
    parser.add_argument(
        "--max-consecutive-failures",
        type=int,
        default=400,
        help="Stop the run if this many sources in a row fail with zero successes in between "
        "(default: 400) -- the signature of a systemic issue (exhausted API balance, an outage) "
        "rather than isolated bad responses. Already-written results stay on disk; rerun to resume.",
    )
    parser.add_argument("--all", action="store_true", help="The whole non-test hard band, not a stratified sample.")
    parser.add_argument("--limit", type=int, help="Only the first N sources after a seeded shuffle (a random pilot).")
    parser.add_argument("--shard", default="0/1", help="i/n: this process handles the sources whose ID hash is i mod n.")
    parser.add_argument("--ids", type=Path, help="only these source IDs (one per line), e.g. an audit sample")
    parser.add_argument("--checkpoint", type=Path, default=HARD_CHECKPOINT_PATH, help="Results JSONL (resumed if it exists).")
    parser.add_argument("--backend", choices=("deepseek", "vllm"), default="deepseek")
    parser.add_argument("--generator-url", default="http://localhost:8000/v1")
    parser.add_argument("--judge-url", default="http://localhost:8001/v1")
    parser.add_argument("--generator-model", default=VLLM_GENERATOR_MODEL)
    parser.add_argument("--judge-model", default=VLLM_JUDGE_MODEL)
    parser.add_argument("--eq-threshold", type=float, default=EQUIVALENCE_THRESHOLD,
                        help="Equivalence gate; recalibrate whenever the judge model changes.")
    parser.add_argument("--num-candidates", type=int, default=NUM_CANDIDATES)
    parser.add_argument("--prompt", choices=tuple(GENERATOR_SIGNATURES), default="base",
                        help="generator instructions: base, or strong (adds STRONG_SIMPLIFICATION)")
    return parser.parse_args()


def _shard_of(source_id: int, n: int) -> int:
    return int(hashlib.md5(str(source_id).encode()).hexdigest(), 16) % n


def main() -> None:
    args = parse_args()

    print("Loading BAREC...")
    df = load_and_clean_barec()
    print(f"  after dropping level 5: {df.shape[0]} sentences")

    global HARD_CHECKPOINT_PATH, EQUIVALENCE_THRESHOLD, NUM_CANDIDATES
    HARD_CHECKPOINT_PATH, EQUIVALENCE_THRESHOLD, NUM_CANDIDATES = args.checkpoint, args.eq_threshold, args.num_candidates

    # BAREC-test is the project's own locked eval set (data/test_manifest.json): excluded here, before
    # anything is generated, not just at export.
    pool = df if args.all else stratified_sample(df, args.sample_fraction, args.seed)
    pool = pool.filter(pl.col("barec_split") != "test")
    print("  routes (non-test):", dict(sorted(pool.group_by("route").len().iter_rows())))
    hard_sample = pool.filter(pl.col("route") == "hard").sample(fraction=1.0, shuffle=True, seed=args.seed)
    shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    if shard_n > 1:
        hard_sample = hard_sample.filter(
            pl.col("ID").map_elements(lambda i: _shard_of(i, shard_n), return_dtype=pl.Int64) == shard_i
        )
    if args.ids:
        hard_sample = hard_sample.filter(pl.col("ID").is_in([int(x) for x in args.ids.read_text().split()]))
    if args.limit:
        hard_sample = hard_sample.head(args.limit)
    print(f"  generating for {hard_sample.shape[0]} hard sources (shard {args.shard}) -> {HARD_CHECKPOINT_PATH}")

    if args.dry_run:
        print("\n--dry-run: stopping before any LM call.")
        return

    generator, equivalence_validator, readability, lexical_scorer = configure_dspy(
        args.backend, args.generator_url, args.judge_url, args.generator_model, args.judge_model, args.prompt,
    )
    print(f"generator {GENERATOR_MODEL_ID} / judge {JUDGE_MODEL_ID}, {NUM_CANDIDATES} candidates, "
          f"eq threshold {EQUIVALENCE_THRESHOLD}")
    hard_results = run_hard_pipeline(
        hard_sample, generator, equivalence_validator, readability, lexical_scorer,
        concurrency=args.concurrency, max_consecutive_failures=args.max_consecutive_failures,
    )

    if hard_results.shape[0] == 0:
        # .mean() on an empty column is None, which can't be :.1%-formatted -- report plainly and
        # stop here rather than crash on that, so a bad run is an honest "0 results", not a traceback.
        print("\nNo hard-band results to report (every attempt failed) -- check the errors above and retry.")
        return

    print(f"\n{hard_results.shape[0]} sources in the checkpoint for this selection")
    print(f"  accepted (tier A+B): {hard_results['passed'].mean():.1%}  tiers: "
          f"{dict(hard_results['acceptance_tier'].value_counts().iter_rows())}")
    print(f"  equivalent: {hard_results['equivalent'].mean():.1%}  lead > 0: {hard_results['readability_passed'].mean():.1%}")
    print(f"  mean lead of accepted: {hard_results.filter(pl.col('passed'))['readability_lead'].mean()}")
    print(f"  sources with >=1 candidate rejected by the structure gates: "
          f"{(hard_results['n_rejected_by_gates'].fill_null(0) > 0).sum()}; "
          f"no eligible candidate at all: {(hard_results['num_passed'] == 0).mean():.1%}")


if __name__ == "__main__":
    main()
