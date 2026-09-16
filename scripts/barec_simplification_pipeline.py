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
   Confirmed necessary against a real pilot run: 28 scripture sentences were
   sent to the generator before this existed, including an actual ayah (with
   its verse number) and a hadith still carrying the Prophet's honorific,
   both reworded. Known gap: this catches BAREC's document-level tagging,
   not a quotation embedded inside some other source's text.
4. Easy and scripture -> identity pairs. No generation, no cost, no risk.
5. Hard -> one DSPy Generator call producing NUM_CANDIDATES candidate
   rewrites, one DSPy equivalence-validator call scoring all of them
   against the original (0.0-1.0 each), and one local MARBERT (ONNX, no
   API call) pass classifying all of them into this pipeline's 1-4 level
   scale -- 2 LM calls per hard sentence total, not NUM_CANDIDATES*3.
   Candidates that land on level 1-2 AND score above EQUIVALENCE_THRESHOLD
   outrank ones that don't; the best-scoring candidate is kept even when
   none of the NUM_CANDIDATES attempts fully pass (same downstream `passed`
   filter as always). See simplify_and_validate()'s docstring for the
   full ranking rule and the TSAR 2025/EhiMeNLP precedent behind
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
import json
import os
from pathlib import Path

# numpy/onnxruntime must be imported before dspy: dspy's lazy-import machinery, if it runs
# first, corrupts numpy's own C-core initialization (TypeError: data type 'bool' not understood)
# in a way that then breaks onnxruntime's internal numpy dependency too. Confirmed by isolating
# the failure -- reordering these two lines above `import dspy` is the entire fix.
import numpy as np
import onnxruntime
import dspy
import polars as pl
from dotenv import load_dotenv
from transformers import AutoTokenizer
from tqdm import tqdm

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BAREC_DIR = PROJECT_ROOT / "data" / "raw" / "barec"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Every successful hard-band result is appended here immediately (one JSON object per line,
# flushed to disk right away) -- not held in memory until the whole run finishes. A run that
# gets interrupted (crash, hang, laptop sleep killing the connection) keeps everything already
# processed, and re-running the script picks up where it left off instead of starting over.
HARD_CHECKPOINT_PATH = PROCESSED_DIR / "barec_hard_pilot_checkpoint.jsonl"

# Superseded by LEVEL_CLASSIFIER_ONNX_PATH below (a fine-tuned local MARBERT classifier beats
# this LLM-prompted one on every measured axis: 86.8-87.5% band accuracy vs. 79.7-83.9%, free
# vs. an API call per classification, and it can't parse-fail the way an LLM response can). Kept
# for reference/comparison -- ClassifyReadabilityLevel and optimize_level_classifier.py still
# work standalone, just no longer wired into this pipeline's configure_dspy().
COMPILED_LEVEL_CLASSIFIER_PATH = PROJECT_ROOT / "scripts" / "compiled" / "level_classifier.json"

# Fine-tuned MARBERT (UBC-NLP/MARBERT), dynamically quantized to int8 ONNX (164MB, ~3.8x
# smaller than the fp32 checkpoint, validated at 95.1% prediction-agreement with the original
# fp32 model, no meaningful accuracy loss). Loaded once in configure_dspy() and reused for every
# candidate's level check -- local CPU inference, no API call, no per-candidate cost, and it's
# the strongest level classifier this project has produced (see memory: level-classifier-benchmark).
LEVEL_CLASSIFIER_ONNX_PATH = PROJECT_ROOT / "models" / "level_classifier_bert_marbert_onnx_int8"
LEVEL_CLASSIFIER_MAX_LENGTH = 128  # matches what the model was fine-tuned and validated with

# Produced by optimize_equivalence_validator.py, which compiles CheckSemanticEquivalence
# against human-annotated ground truth via MIPROv2 -- loaded automatically below if present.
COMPILED_EQUIVALENCE_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "compiled" / "equivalence_validator.json"

DEEPSEEK_MODEL = "deepseek/deepseek-flash"  # DeepSeek V4.1 Flash's current API model id.
# Confirmed via DeepSeek's own docs: the legacy name "deepseek-v4-flash" still works but is a
# deprecated alias that routes to this same model; "deepseek-flash" is the current, correct id.

KEEP_COLS = ["ID", "Sentence", "Word_Count", "Readability_Level_5", "Domain", "Source", "Text_Class"]

# This pipeline's readability scale is BAREC's 5-level collapse with level 5 dropped, so 4
# levels remain (1 = simplest ... 4 = hardest). This is NOT BAREC's native 19-level scale --
# don't conflate the two when reading or editing the prompts below.
EASY_LEVELS = (1, 2)
HARD_LEVELS = (3, 4)
EASY_LEVEL_CEILING = 2  # a generated pair passes the level check if predicted_level <= this

# CheckSemanticEquivalence outputs a continuous 0.0-1.0 score, not a boolean -- this threshold
# is what simplify_and_validate() uses to derive the pass/fail gate (and, now, to break ties
# among reranked candidates). Calibrated from data/processed/equivalence_validator_eval_results.parquet
# (the MIPROv2-compiled validator's real predictions on the 25-pair held-out annotated set): a
# threshold sweep found 0.70-0.75 as a broad, stable optimum (84% accuracy there vs. 64% at the
# original guessed 0.8), meaning the compiled validator's scores run a bit more conservative than
# a naive 0.8 cutoff assumed -- consistent with the earlier finding that the raw zero-shot judge
# was already biased toward over-flagging valid simplifications as "not equivalent". Picked 0.7
# (the lower/safer edge of that plateau) rather than the exact sweep peak, since the sweep itself
# was measured on the same 25-example set being reported -- treat as directional, not exact;
# revisit with more annotations.
EQUIVALENCE_THRESHOLD = 0.7

# Reranking: generate this many candidate simplifications per hard sentence and keep the
# best-scoring one, instead of generating once and gating pass/fail -- informed by the TSAR 2025
# Shared Task's winning system (EhiMeNLP: generate multiple candidates, then rerank by
# readability + semantic similarity, no parallel training data required). Real cost multiplier:
# NUM_CANDIDATES generations + NUM_CANDIDATES x 2 validations per hard sentence, i.e. 5x the
# call volume (and $ cost) of the original single-candidate pipeline.
NUM_CANDIDATES = 5

# Quranic verses, hadith, and biblical text must be preserved verbatim regardless of assessed
# difficulty -- these are canonical/scriptural text, not prose to be paraphrased. Confirmed via
# the completed pilot: 28 sentences from these sources were sent to the generator before this
# guard existed, including an actual ayah (with its verse number) and a hadith still carrying
# the Prophet's honorific, both reworded. BAREC tags this cleanly by Source; routed as identity
# pairs unconditionally, the same mechanism already used for the easy band, just triggered by a
# different reason (canonical text, not "already simple"). Known gap: this catches BAREC's
# document-level tagging, not a quotation embedded inside some other source's text.
SCRIPTURE_SOURCES = {"Quran", "Hadith", "Old Testament", "New Testament"}


# --------------------------------------------------------------------------------------
# Data loading / cleaning / sampling
# --------------------------------------------------------------------------------------


def load_and_clean_barec() -> pl.DataFrame:
    splits = [pl.read_csv(BAREC_DIR / f"{name}.csv", encoding="utf8-lossy") for name in ("train", "dev", "test")]
    df = pl.concat(splits).select(KEEP_COLS)
    df = df.filter(pl.col("Readability_Level_5") != 5)
    return df


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
# Local level classifier (MARBERT, ONNX, int8) -- pure onnxruntime + numpy, no torch. optimum's
# ORTModelForSequenceClassification would also work but pulls in torch for its tensor glue even
# though the actual compute runs through onnxruntime either way; running the .onnx graph and
# tokenizer output directly as numpy arrays gets the same result without that dependency weight.
# --------------------------------------------------------------------------------------


class LocalLevelClassifier:
    def __init__(self, onnx_path: Path):
        self.session = onnxruntime.InferenceSession(str(onnx_path / "model_quantized.onnx"))
        self.tokenizer = AutoTokenizer.from_pretrained(str(onnx_path))

    def classify(self, texts: list[str]) -> list[int]:
        """Batched: one onnxruntime call for however many texts are passed, not one call each."""
        inputs = self.tokenizer(
            texts, return_tensors="np", truncation=True, max_length=LEVEL_CLASSIFIER_MAX_LENGTH, padding=True
        )
        onnx_inputs = {k: v for k, v in inputs.items() if k in {i.name for i in self.session.get_inputs()}}
        (logits,) = self.session.run(None, onnx_inputs)
        return (np.argmax(logits, axis=-1) + 1).tolist()  # argmax is 0-indexed; levels are 1-4


# --------------------------------------------------------------------------------------
# DSPy signatures
#
# A dspy.Signature's docstring IS the task instruction DSPy compiles into the actual
# prompt; each field's `desc` is the per-field guidance. CheckSemanticEquivalence is
# MIPROv2-compiled against human-annotated ground truth (optimize_equivalence_validator.py);
# ClassifyReadabilityLevel is defined here for reference/comparison but no longer wired into
# this pipeline (see LEVEL_CLASSIFIER_ONNX_PATH's comment). Both the generator and the
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
    Reduce unnecessary subordinate clauses. Where a clearer phrasing
    exists, prefer it over a phrasing that stacks many attached
    prefixes/suffixes onto one word.

    Do not add, remove, or alter any fact, entity, number, name, date, or
    claim from the source sentence. Do not add explanations, examples, or
    commentary that were not in the source. Do not soften, strengthen, or
    otherwise shift the original meaning. Preserve negation exactly. If a
    technical or proper term cannot be simplified without changing its
    meaning, keep the term as-is rather than inventing an inaccurate
    substitute.

    Output grammatically correct Modern Standard Arabic only -- no dialect,
    no other language, no transliteration.

    Make the candidates genuinely different from each other -- vary word
    choice, sentence order, and how (or whether) the sentence is split into
    more than one -- not near-duplicates that differ only in punctuation or
    a single synonym swap. Different candidates are only useful for
    reranking if they actually represent different simplification attempts.
    """

    original_text: str = dspy.InputField(
        desc="A single Modern Standard Arabic sentence at level 3 or 4 of this pipeline's 4-level scale."
    )
    simplified_candidates: list[str] = dspy.OutputField(
        desc=f"Exactly {NUM_CANDIDATES} different candidate rewrites of original_text, each one "
        "independently rewritten to level 1 or 2 of this pipeline's 4-level scale, each preserving "
        "the original's meaning exactly. The candidates must be meaningfully different from each "
        "other, not trivial variants."
    )


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


def configure_dspy() -> tuple[dspy.Module, dspy.Module, LocalLevelClassifier]:
    """Build the generator, the equivalence validator, and the local level classifier.

    Generation gets a higher temperature (varied phrasing is fine, even
    desirable, and NUM_CANDIDATES candidates in one call need genuine
    variety to be worth reranking); the equivalence judge gets temperature 0
    (consistent verdicts matter more than varied ones for a judge). Level
    classification no longer goes through an LLM call at all -- see
    LEVEL_CLASSIFIER_ONNX_PATH's comment for why the local MARBERT model
    replaced it (more accurate, free, can't parse-fail).
    """
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and "
            "fill it in, or export it directly, e.g.:\n  export DEEPSEEK_API_KEY=sk-...\n"
            "(--dry-run doesn't need it.)"
        )

    # thinking={"type": "disabled"}: DeepSeek V4.1 Flash defaults to an internal "thinking" pass
    # (returned in a separate reasoning_content field) that, left on, consumed the entire
    # max_tokens budget on nearly every call before the model ever wrote the actual structured
    # answer DSPy needs -- confirmed against the real API as the cause of near-total call
    # failure. Disabling it is what our own dspy.ChainOfThought "reasoning" field is already
    # for; the two were fighting over the same token budget.
    # timeout=90: without this, a request that stalls (e.g. the underlying connection dying
    # silently -- confirmed to happen across a laptop sleep/resume) hangs indefinitely instead
    # of failing. A failure gets caught and skipped by run_hard_pipeline's own try/except; a
    # hang blocks the whole run with no way to recover short of killing the process.
    common_kwargs = dict(api_key=api_key, thinking={"type": "disabled"}, timeout=90)
    # max_tokens=2048: generation now produces NUM_CANDIDATES=5 candidates in one response
    # instead of one, so it needs real headroom over the original single-candidate 1024 budget.
    generation_lm = dspy.LM(DEEPSEEK_MODEL, temperature=0.7, max_tokens=2048, **common_kwargs)
    # max_tokens=4096: the equivalence judge now returns NUM_CANDIDATES=5 reasoning strings AND
    # 5 scores in one response (batched scoring, see CheckSemanticEquivalence's docstring) --
    # substantially more output per call than the single reasoning+score pair the original
    # 1024/2048 budgets were sized for. Explicitly tested at 4096 with thinking mode disabled
    # (this is a different setting than the thinking-mode experiment that failed at the same
    # 4096 ceiling -- that failure was thinking eating the whole budget before writing the
    # visible answer at all; plain (non-thinking) longer structured output is a different,
    # much more predictable consumer of the same budget).
    judge_lm = dspy.LM(DEEPSEEK_MODEL, temperature=0.0, max_tokens=4096, **common_kwargs)
    # use_json_adapter_fallback=False: DSPy's default behavior retries a parse failure via a
    # JSON-mode adapter, which sends a `response_format` param DeepSeek's endpoint currently
    # rejects (confirmed against the real API) -- turning a single truncated/malformed response
    # into a fatal crash instead of a recoverable one. Plain ChatAdapter parses our fields fine
    # on its own; max_tokens raised from 512 to reduce how often truncation triggers this at all.
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

    level_classifier = LocalLevelClassifier(LEVEL_CLASSIFIER_ONNX_PATH)
    print(f"loaded local MARBERT level classifier from {LEVEL_CLASSIFIER_ONNX_PATH}")

    return generator, equivalence_validator, level_classifier


def simplify_and_validate(
    generator: dspy.Module,
    equivalence_validator: dspy.Module,
    level_classifier: LocalLevelClassifier,
    original_text: str,
) -> dict:
    """Generate NUM_CANDIDATES simplifications in ONE call, score all of them for equivalence in
    ONE call, classify all of them locally (free, no API call), and keep the best-scoring one --
    2 API calls per hard sentence total, not NUM_CANDIDATES*3 (see NUM_CANDIDATES's own comment
    for the TSAR 2025/EhiMeNLP precedent behind generating multiple candidates and reranking).

    Ranking: candidates that pass both checks (equivalent AND easy) always outrank ones that
    don't; within either group, the higher equivalence_score wins. This means: if ANY candidate
    passes, we return the most faithful passing one; if NONE pass, we still return the most
    faithful failure available (a better fallback than an arbitrary single attempt) rather than
    nothing -- downstream code still filters on `passed`, so a non-passing "best of 5" is
    handled exactly like a non-passing single attempt always was.

    Defensive against list-length mismatches: batched list outputs are a real new failure mode a
    single-field output never had (the model can under/over-generate items, or the three lists
    -- candidates, scores, reasoning -- can come back different lengths). We use only the
    shortest common length across whatever came back rather than assuming NUM_CANDIDATES items
    are always present, and raise if that leaves nothing scorable at all (caught by
    run_hard_pipeline's existing per-sentence try/except, same as any other failure).
    """
    gen_out = generator(original_text=original_text)
    candidate_texts = list(gen_out.simplified_candidates)[:NUM_CANDIDATES]
    if not candidate_texts:
        raise ValueError("generator returned zero candidates")

    eq_out = equivalence_validator(original_text=original_text, simplified_candidates=candidate_texts)
    scores = list(eq_out.equivalence_scores)
    reasons = list(eq_out.reasoning_per_candidate)

    n = min(len(candidate_texts), len(scores), len(reasons))  # shortest common length -- see docstring
    if n == 0:
        raise ValueError(
            f"equivalence validator returned mismatched/empty lists: "
            f"{len(candidate_texts)} candidates, {len(scores)} scores, {len(reasons)} reasons"
        )
    candidate_texts, scores, reasons = candidate_texts[:n], scores[:n], reasons[:n]

    predicted_levels = level_classifier.classify(candidate_texts)  # one batched local call, all n at once

    candidates = []
    for text, raw_score, reasoning, predicted_level in zip(candidate_texts, scores, reasons, predicted_levels):
        equivalence_score = max(0.0, min(1.0, float(raw_score)))  # clamp against a judge that
        # ignores the 0.0-1.0 instruction and returns something out of range
        equivalent = equivalence_score >= EQUIVALENCE_THRESHOLD
        is_easy = predicted_level <= EASY_LEVEL_CEILING
        candidates.append(
            {
                "simplified_text": text,
                "equivalence_score": equivalence_score,
                "equivalent": equivalent,
                "equivalence_reasoning": str(reasoning),
                "predicted_level": predicted_level,
                "is_easy": is_easy,
                "passed": equivalent and is_easy,
            }
        )

    best = max(candidates, key=lambda c: (c["passed"], c["equivalence_score"]))
    num_passed = sum(1 for c in candidates if c["passed"])

    return {
        "original_text": original_text,
        "simplified_text": best["simplified_text"],
        "equivalence_score": best["equivalence_score"],
        "equivalent": best["equivalent"],
        "equivalence_reasoning": best["equivalence_reasoning"],
        "predicted_level": best["predicted_level"],
        "is_easy": best["is_easy"],
        "passed": best["passed"],
        "num_candidates": len(candidates),
        "num_passed": num_passed,
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
    return rows


def run_hard_pipeline(
    hard_sample: pl.DataFrame,
    generator: dspy.Module,
    equivalence_validator: dspy.Module,
    level_classifier: LocalLevelClassifier,
) -> pl.DataFrame:
    HARD_CHECKPOINT_PATH.parent.mkdir(parents=True, exist_ok=True)

    done = load_checkpoint()
    done_ids = {row["ID"] for row in done}
    if done_ids:
        print(f"resuming: {len(done_ids)} hard sentences already completed in a prior run "
              f"(from {HARD_CHECKPOINT_PATH})")

    remaining = hard_sample.filter(~pl.col("ID").is_in(done_ids))

    failures = 0
    # Append mode + flush after every write: each result is safely on disk the moment it's
    # produced, not batched in memory until the whole run finishes.
    with open(HARD_CHECKPOINT_PATH, "a", encoding="utf-8") as f:
        for row in tqdm(remaining.iter_rows(named=True), total=remaining.shape[0], desc="hard band"):
            try:
                result = simplify_and_validate(generator, equivalence_validator, level_classifier, row["Sentence"])
            except Exception as e:
                # A single truncated/malformed LM response (or, tonight, a stalled connection
                # after the machine slept) shouldn't kill a run that's already spent real API
                # calls on everything before it -- log and move on.
                failures += 1
                tqdm.write(f"  skipped ID {row['ID']}: {type(e).__name__}: {str(e)[:150]}")
                continue
            result["ID"] = row["ID"]
            result["source_level"] = row["Readability_Level_5"]
            f.write(json.dumps(result, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    if failures:
        print(f"{failures} / {remaining.shape[0]} hard sentences failed and were skipped this run")

    checkpoint_rows = load_checkpoint()
    if not checkpoint_rows:
        # Every attempt failed (or this is a fresh run with nothing to resume) -- pl.DataFrame([])
        # has no columns at all, so filtering on "ID" below would crash with ColumnNotFoundError
        # rather than reporting "0 succeeded" cleanly. A real network outage hit 20/20 failures
        # here once already; this shouldn't be a stack trace when it happens again.
        print("WARNING: no hard-band results at all (every attempt failed, or nothing has run yet).")
        return pl.DataFrame(schema={"ID": pl.Int64, "passed": pl.Boolean, "equivalent": pl.Boolean, "is_easy": pl.Boolean})
    all_done = pl.DataFrame(checkpoint_rows)
    # Guard against a stale checkpoint from a run with different --sample-fraction/--seed:
    # only return rows that are actually part of *this* run's hard_sample.
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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    print("Loading BAREC...")
    df = load_and_clean_barec()
    print(f"  after dropping level 5: {df.shape[0]} sentences")

    sample = stratified_sample(df, args.sample_fraction, args.seed)
    is_scripture = pl.col("Source").is_in(SCRIPTURE_SOURCES)
    # Scripture is routed out regardless of level -- preserved verbatim for canonicity, not
    # because it's assessed as easy. Only non-scripture hard-band sentences reach the generator.
    scripture_sample = sample.filter(is_scripture)
    easy_sample = sample.filter(~is_scripture & pl.col("Readability_Level_5").is_in(EASY_LEVELS))
    hard_sample = sample.filter(~is_scripture & pl.col("Readability_Level_5").is_in(HARD_LEVELS))
    print(
        f"  {args.sample_fraction:.1%} stratified sample: {sample.shape[0]} sentences "
        f"({easy_sample.shape[0]} easy / {hard_sample.shape[0]} hard / "
        f"{scripture_sample.shape[0]} scripture, preserved regardless of level)"
    )

    easy_pairs = build_identity_pairs(easy_sample, "identity")
    scripture_pairs = build_identity_pairs(scripture_sample, "scripture")

    calls_per_sentence = 2  # 1 batched generation call (NUM_CANDIDATES candidates) + 1 batched
    # equivalence-scoring call (all NUM_CANDIDATES candidates) -- level classification is local
    # (MARBERT, ONNX), not an API call, so it doesn't add to this count regardless of NUM_CANDIDATES.
    if args.dry_run:
        print("\n--dry-run: stopping before any LM call.")
        print(f"Would run {hard_sample.shape[0]} hard sentences x {calls_per_sentence} LM calls each "
              f"(reranking {NUM_CANDIDATES} candidates/sentence, batched) = {hard_sample.shape[0] * calls_per_sentence} total calls.")
        return

    print("\nConfiguring DSPy (DeepSeek V4.1 Flash)...")
    generator, equivalence_validator, level_classifier = configure_dspy()

    print(f"Running hard band ({hard_sample.shape[0]} sentences x {calls_per_sentence} calls each, reranking {NUM_CANDIDATES} candidates, batched)...")
    hard_results = run_hard_pipeline(hard_sample, generator, equivalence_validator, level_classifier)

    if hard_results.shape[0] == 0:
        # Every attempt failed (confirmed real cause once already: a network outage took out
        # 20/20 calls with DNS resolution errors, nothing to do with the pipeline logic itself).
        # .mean() on an empty column is None, which can't be :.1%-formatted -- report plainly and
        # stop here rather than crash on that, so a bad run is an honest "0 results", not a traceback.
        print("\nNo hard-band results to report (every attempt failed) -- check the errors above and retry.")
        return

    print(f"\npass rate: {hard_results['passed'].mean():.1%}")
    print(f"  equivalence pass rate: {hard_results['equivalent'].mean():.1%}")
    print(f"  easy-band pass rate: {hard_results['is_easy'].mean():.1%}")
    # num_passed=0 means none of the NUM_CANDIDATES attempts passed for that sentence (we still
    # returned the best-scoring failure) -- worth knowing separately from the overall pass rate,
    # since it's the "reranking couldn't rescue this one at all" rate, not just "didn't win the tiebreak."
    print(f"  sentences where 0/{NUM_CANDIDATES} candidates passed: {(hard_results['num_passed'] == 0).mean():.1%}")

    hard_pairs = hard_results.filter(pl.col("passed")).select(
        pl.col("ID"),
        pl.col("original_text"),
        pl.col("simplified_text"),
        pl.col("source_level"),
        pl.col("predicted_level"),
        pl.col("equivalent"),
        pl.col("equivalence_reasoning"),
        pl.col("is_easy"),
        pl.lit("generated").alias("pair_type"),
    )

    pilot_dataset = pl.concat([easy_pairs, scripture_pairs, hard_pairs])
    print(
        f"\npilot dataset: {pilot_dataset.shape[0]} pairs "
        f"({easy_pairs.shape[0]} identity + {scripture_pairs.shape[0]} scripture + "
        f"{hard_pairs.shape[0]} generated)"
    )

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    pilot_dataset.write_parquet(PROCESSED_DIR / "barec_simplification_pilot.parquet")
    hard_results.write_parquet(PROCESSED_DIR / "barec_hard_pilot_raw_results.parquet")
    print(f"saved pilot_dataset and raw hard-band results to {PROCESSED_DIR}/")


if __name__ == "__main__":
    main()
