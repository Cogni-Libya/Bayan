"""Validators for generated Arabic simplification pairs (original -> simplified).

How this project decides whether a generated pair is usable, as a standalone module: the same
checks and thresholds as barec_simplification_pipeline.py (which still carries its own copy), but
importing this does not pull in the generation pipeline.

What is measured
----------------
1. Semantic equivalence -- LLM judge (DeepSeek via DSPy, one API call per original). Score in
   [0.0, 1.0] for how completely the simplified text preserves the original's meaning (facts,
   entities, numbers, negation; rewording/shortening is NOT penalised). `equivalent` means
   score >= EQUIVALENCE_THRESHOLD (0.7). The judge is CheckSemanticEquivalence, MIPROv2-compiled
   against human-annotated pairs (scripts/compiled/equivalence_validator.json).
2. Readability -- CAMeL Lab's BAREC model (CAMeL-Lab/readability-arabertv02-word-CE, 19 levels; runs
   locally, no API call; see camel_readability.py). It scores the ORIGINAL and the SIMPLIFIED text
   separately and the pair passes when the simplified text got easier:
   d_logit = logit P(easy | simplified) - logit P(easy | original) >= TAU (0.33). P(easy) is the summed
   probability of BAREC levels 1-11, i.e. levels 1-2 of the 5-level scale. `predicted_level` (5-level
   scale, simplified text) and `is_easy` (level <= 2) are informational, not part of the gate: an absolute
   band rule rejected 41% of the human-written simplifications in SAMER (measured with the previous
   readability check) and accepts texts that were never simplified at all.
3. Gate -- `passed = equivalent and readability_passed`.

Known limits (report these alongside any numbers built on the gate)
- Equivalence: on the 25-pair annotated held-out set the compiled judge rejected nothing (0 true
  negatives; see README "Where we stand"), so its ability to catch meaning drift is unproven --
  read `equivalent` as "not flagged by the judge", not "verified". The 0.7 threshold was picked
  from a sweep on those same 25 pairs (0.70-0.75 plateau, 84% accuracy vs 64% at 0.8):
  directional only. Fixing this on real negatives is an open README item.
- Readability: a filter, not an independent judge, with a ceiling of about 80%. On SAMER (human
  simplifications; evaluation only) CAMeL ranks the simplified version above the original 80.1% of
  the time for sentence pairs and 76.9% for single-word swaps; the other BAREC-trained encoders we
  tried score 72-77%, and every model is worse when the simple version is longer. It is noisy on light edits (only 61% of the "light" pairs in Marwan's set rise by TAU).
  TAU = 0.33 was chosen on SAMER's test split (about 10% of the human pairs, reversed, would pass),
  so it is a default, not a calibrated final value. Texts are scored one at a time in fp32 on CPU,
  so a label never depends on its batch neighbours (the previous int8 check's did).

Library use (from another script in scripts/):
    from validation import load_equivalence_validator, load_readability_classifier, validate_pairs, summarize
    df = validate_pairs(originals, simplified, load_equivalence_validator(), load_readability_classifier())
    print(summarize(df))

Command line -- score any .jsonl/.csv/.parquet with original_text and simplified_text columns:
    uv run python scripts/validation.py pairs.jsonl --out data/processed/pairs_validated.parquet
    uv run python scripts/validation.py pairs.jsonl --skip-equivalence     # readability only: local, free
    uv run python scripts/validation.py pairs.jsonl --limit 50             # small paid test first

Output keeps every input column and adds val_* columns (prefixed so they never overwrite the
input's own scores). The equivalence stage calls the DeepSeek API (needs DEEPSEEK_API_KEY, via the
environment or a project-root .env); it checkpoints as it goes and resumes if interrupted.

The readability model needs no manual setup. The first run downloads it and, on CPU, exports it to
ONNX once (about a minute; cached in models/camel_readability_arabertv02_word_onnx/, so later runs
start at once); with an NVIDIA GPU it runs in torch on CUDA instead (--device cpu|cuda|auto).
`uv sync` installs torch with its CUDA libraries on Linux; on a CPU-only machine you can skip them with
`uv venv` and `UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu UV_INDEX_STRATEGY=unsafe-best-match
uv pip install -r pyproject.toml`, then run with `uv run --no-sync` (a plain `uv run` re-syncs to the lockfile).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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
from tqdm import tqdm

from camel_readability import CamelReadability

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# Produced by optimize_equivalence_validator.py, which compiles CheckSemanticEquivalence against
# human-annotated ground truth via MIPROv2 -- loaded automatically if present.
COMPILED_EQUIVALENCE_VALIDATOR_PATH = PROJECT_ROOT / "scripts" / "compiled" / "equivalence_validator.json"

DEEPSEEK_MODEL = "deepseek/deepseek-flash"  # DeepSeek V4.1 Flash's current API model id
# ("deepseek-v4-flash" still works but is a deprecated alias for the same model).

# Readability gate: the simplified text's P(easy) must rise over the original's by at least TAU (logit units).
# Chosen on SAMER's test split so that about 10% of the human-written simplifications, REVERSED (made harder),
# would still pass (TAU 0.7 gives about 5%). A default, not a calibrated final value.
TAU = 0.33

# `predicted_level` is BAREC's 5-level scale (1 = simplest ... 5 = hardest), mapped from CAMeL's 19 levels.
EASY_LEVEL_CEILING = 2  # informational `is_easy`: predicted_level <= this

# CheckSemanticEquivalence outputs a continuous 0.0-1.0 score; this threshold derives the
# equivalent/not-equivalent decision. Calibrated on the compiled validator's predictions for the
# 25-pair held-out annotated set (data/processed/equivalence_validator_eval_results.parquet): a
# sweep found 0.70-0.75 as a broad optimum (84% accuracy vs 64% at an initially guessed 0.8) --
# the compiled validator's scores run more conservative than a naive 0.8 cutoff assumes. Picked
# 0.7, the safer edge of that plateau, since the sweep used the same 25 examples it is reported
# on: treat as directional, not exact.
EQUIVALENCE_THRESHOLD = 0.7


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


def make_deepseek_lm(temperature: float, max_tokens: int) -> dspy.LM:
    load_dotenv(PROJECT_ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is not set. Copy .env.example to .env at the project root and "
            "fill it in, or export it directly, e.g.:\n  export DEEPSEEK_API_KEY=sk-..."
        )
    # thinking disabled: DeepSeek V4.1 Flash defaults to an internal "thinking" pass that, left on,
    # consumed the entire max_tokens budget on nearly every call before writing the structured
    # answer DSPy needs -- confirmed against the real API as the cause of near-total call failure.
    # timeout=90: a stalled connection (confirmed across a laptop sleep/resume) otherwise hangs
    # the whole run indefinitely instead of failing that one call.
    return dspy.LM(
        DEEPSEEK_MODEL, temperature=temperature, max_tokens=max_tokens,
        api_key=api_key, thinking={"type": "disabled"}, timeout=90,
    )


def load_equivalence_validator() -> dspy.Module:
    """Judge at temperature 0 (consistent verdicts matter more than varied ones), loading the
    MIPROv2-compiled program when present. dspy.Predict, not ChainOfThought: the signature already
    declares its own reasoning_per_candidate field ahead of the scores, and wrapping it in
    ChainOfThought would add a redundant second reasoning field. max_tokens=4096 because one
    response carries a reasoning string and a score for every candidate."""
    # use_json_adapter_fallback=False: DSPy's default retries a parse failure through a JSON-mode
    # adapter, which sends a `response_format` param DeepSeek's endpoint rejects -- turning one
    # malformed response into a fatal crash instead of a recoverable one.
    dspy.configure(adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))
    validator = dspy.Predict(CheckSemanticEquivalence)
    if COMPILED_EQUIVALENCE_VALIDATOR_PATH.exists():
        validator.load(str(COMPILED_EQUIVALENCE_VALIDATOR_PATH))
        print(f"loaded optimized equivalence validator from {COMPILED_EQUIVALENCE_VALIDATOR_PATH}")
    else:
        print(
            f"no compiled equivalence validator at {COMPILED_EQUIVALENCE_VALIDATOR_PATH} -- using "
            "it zero-shot. Run optimize_equivalence_validator.py first to calibrate it against "
            "human-annotated ground truth."
        )
    validator.set_lm(make_deepseek_lm(temperature=0.0, max_tokens=4096))
    return validator


def load_readability_classifier(device: str | None = None) -> CamelReadability:
    """CAMeL readability model: torch on a GPU, cached ONNX on CPU (the first CPU run exports it once)."""
    classifier = CamelReadability(device)
    print(f"loaded the CAMeL readability model on {classifier.device}")
    return classifier


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def apply_gate(equivalence_score: float, d_logit: float, tau: float = TAU) -> dict:
    equivalence_score = max(0.0, min(1.0, float(equivalence_score)))  # clamp against a judge that
    # ignores the 0.0-1.0 instruction and returns something out of range
    equivalent = equivalence_score >= EQUIVALENCE_THRESHOLD
    readability_passed = d_logit >= tau
    return {
        "equivalence_score": equivalence_score,
        "equivalent": equivalent,
        "d_logit": d_logit,
        "readability_passed": readability_passed,
        "passed": equivalent and readability_passed,
    }


def score_equivalence(
    equivalence_validator: dspy.Module, original_text: str, candidate_texts: list[str]
) -> list[tuple[float, str]]:
    """(clamped score, reasoning) per candidate, from one API call. Defensive against list-length
    mismatches, a real failure mode of batched list outputs (the model can under/over-generate
    items, or scores and reasoning can come back different lengths): keeps only the shortest
    common length, and raises if that leaves nothing scorable."""
    out = equivalence_validator(original_text=original_text, simplified_candidates=candidate_texts)
    scores = list(out.equivalence_scores)
    reasons = list(out.reasoning_per_candidate)
    n = min(len(candidate_texts), len(scores), len(reasons))
    if n == 0:
        raise ValueError(
            f"equivalence validator returned mismatched/empty lists: "
            f"{len(candidate_texts)} candidates, {len(scores)} scores, {len(reasons)} reasons"
        )
    return [(max(0.0, min(1.0, float(s))), str(r)) for s, r in zip(scores[:n], reasons[:n])]


def score_readability(
    readability: CamelReadability, originals: list[str], simplified: list[str], show_progress: bool = False
) -> dict[str, np.ndarray]:
    """Per pair: P(easy) of the original and of the simplified text, d_logit, and the simplified text's
    5-level level. Every distinct text is scored once, on its own."""
    texts = list(dict.fromkeys(originals + simplified))
    probs = readability.predict_probs(texts, show_progress=show_progress)
    p_easy, levels = readability.p_easy(probs), readability.levels(probs)
    index = {t: i for i, t in enumerate(texts)}
    o = np.array([index[t] for t in originals], dtype=int)
    s = np.array([index[t] for t in simplified], dtype=int)
    return {"p_easy_original": p_easy[o], "p_easy_simplified": p_easy[s],
            "d_logit": _logit(p_easy[s]) - _logit(p_easy[o]), "predicted_level": levels[s]}


def score_candidates(
    equivalence_validator: dspy.Module,
    readability: CamelReadability,
    original_text: str,
    candidate_texts: list[str],
    tau: float = TAU,
) -> list[dict]:
    """Full validation of several candidates for ONE original: one batched equivalence call plus
    local readability scoring. Returns one dict per scored candidate (see apply_gate)."""
    scored = score_equivalence(equivalence_validator, original_text, candidate_texts)
    texts = candidate_texts[:len(scored)]
    r = score_readability(readability, [original_text] * len(texts), texts)
    return [
        {"simplified_text": text, "equivalence_reasoning": reasoning,
         "p_easy_original": float(r["p_easy_original"][i]), "p_easy_simplified": float(r["p_easy_simplified"][i]),
         "predicted_level": int(r["predicted_level"][i]), "is_easy": bool(r["predicted_level"][i] <= EASY_LEVEL_CEILING),
         **apply_gate(score, float(r["d_logit"][i]), tau)}
        for i, (text, (score, reasoning)) in enumerate(zip(texts, scored))
    ]


def _pair_key(original: str, simplified: str) -> str:
    return hashlib.sha1(f"{original}\x00{simplified}".encode("utf-8")).hexdigest()


def _load_checkpoint(path: Path) -> dict[str, dict]:
    done: dict[str, dict] = {}
    if path.exists():
        with open(path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    row = json.loads(line)
                    if row.get("error") is None:  # failed rows are retried on resume
                        done[row["key"]] = row
    return done


def validate_pairs(
    originals: list[str],
    simplified: list[str],
    equivalence_validator: dspy.Module | None = None,
    readability: CamelReadability | None = None,
    workers: int = 8,
    checkpoint_path: Path | None = None,
    tau: float = TAU,
) -> pl.DataFrame:
    """Score (original, simplified) pairs; one output row per pair, same order. Pass None for a
    validator to skip that check (its columns come back null, and val_passed is null unless both
    ran). A failed API call yields a null score and the message in val_error -- it never aborts
    the run."""
    n = len(originals)
    assert len(simplified) == n
    out: dict[str, list] = {
        "val_equivalence_score": [None] * n, "val_equivalent": [None] * n,
        "val_equivalence_reasoning": [None] * n, "val_p_easy_original": [None] * n,
        "val_p_easy_simplified": [None] * n, "val_d_logit": [None] * n, "val_readability_passed": [None] * n,
        "val_predicted_level": [None] * n, "val_is_easy": [None] * n, "val_error": [None] * n,
    }

    if readability is not None:
        r = score_readability(readability, originals, simplified, show_progress=True)
        for i in range(n):
            out["val_p_easy_original"][i] = float(r["p_easy_original"][i])
            out["val_p_easy_simplified"][i] = float(r["p_easy_simplified"][i])
            out["val_d_logit"][i] = float(r["d_logit"][i])
            out["val_readability_passed"][i] = bool(r["d_logit"][i] >= tau)
            out["val_predicted_level"][i] = int(r["predicted_level"][i])
            out["val_is_easy"][i] = bool(r["predicted_level"][i] <= EASY_LEVEL_CEILING)

    if equivalence_validator is not None:
        keys = [_pair_key(o, s) for o, s in zip(originals, simplified)]
        done = _load_checkpoint(checkpoint_path) if checkpoint_path else {}
        lock = threading.Lock()
        ckpt = open(checkpoint_path, "a", encoding="utf-8") if checkpoint_path else None

        def apply(i: int, score, reasoning, error) -> None:
            if score is not None:
                out["val_equivalence_score"][i] = score
                out["val_equivalent"][i] = score >= EQUIVALENCE_THRESHOLD
                out["val_equivalence_reasoning"][i] = reasoning
            out["val_error"][i] = error

        def work(i: int):
            try:
                (score, reasoning), = score_equivalence(equivalence_validator, originals[i], [simplified[i]])[:1]
                return i, score, reasoning, None
            except Exception as e:  # noqa: BLE001 -- one bad call must not abort a multi-thousand-row run
                return i, None, None, f"{type(e).__name__}: {e}"[:300]

        todo = []
        for i, key in enumerate(keys):
            if key in done:
                apply(i, done[key]["score"], done[key]["reasoning"], None)
            else:
                todo.append(i)
        if done:
            print(f"resuming: {n - len(todo)} of {n} pairs already scored in {checkpoint_path}")
        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(work, i) for i in todo]
                for fut in tqdm(as_completed(futures), total=len(futures), desc="equivalence"):
                    i, score, reasoning, error = fut.result()
                    apply(i, score, reasoning, error)
                    if ckpt:
                        with lock:
                            ckpt.write(json.dumps({"key": keys[i], "score": score, "reasoning": reasoning,
                                                   "error": error}, ensure_ascii=False) + "\n")
                            ckpt.flush()
        finally:
            if ckpt:
                ckpt.close()

    out["val_passed"] = [
        (e and z) if e is not None and z is not None else None
        for e, z in zip(out["val_equivalent"], out["val_readability_passed"])
    ]
    return pl.DataFrame(out, schema={
        "val_equivalence_score": pl.Float64, "val_equivalent": pl.Boolean,
        "val_equivalence_reasoning": pl.Utf8, "val_p_easy_original": pl.Float64,
        "val_p_easy_simplified": pl.Float64, "val_d_logit": pl.Float64, "val_readability_passed": pl.Boolean,
        "val_predicted_level": pl.Int64, "val_is_easy": pl.Boolean, "val_error": pl.Utf8,
        "val_passed": pl.Boolean,
    })


def summarize(df: pl.DataFrame) -> dict:
    """Aggregate metrics over validate_pairs() output. Rates are over rows where that check ran."""
    def rate(col: str):
        s = df[col].drop_nulls()
        return float(s.cast(pl.Float64).mean()) if s.len() else None

    return {
        "pairs": df.height,
        "equivalence_scored": int(df["val_equivalence_score"].drop_nulls().len()),
        "equivalence_failed": int(df["val_error"].drop_nulls().len()),
        "mean_equivalence_score": rate("val_equivalence_score"),
        "equivalent_rate": rate("val_equivalent"),
        "readability_passed_rate": rate("val_readability_passed"),
        "mean_d_logit": rate("val_d_logit"),
        "easy_rate": rate("val_is_easy"),
        "passed_rate": rate("val_passed"),
        "level_distribution": {int(k): int(v) for k, v in
                               df["val_predicted_level"].drop_nulls().value_counts().iter_rows()},
    }


def format_summary(s: dict) -> str:
    def pct(x):
        return "n/a" if x is None else f"{x:.1%}"

    lines = [
        f"pairs: {s['pairs']}   equivalence scored: {s['equivalence_scored']}   failed: {s['equivalence_failed']}",
        f"equivalent (score >= {EQUIVALENCE_THRESHOLD}): {pct(s['equivalent_rate'])}"
        + ("" if s["mean_equivalence_score"] is None else f"   (mean score {s['mean_equivalence_score']:.3f})"),
        f"readability rose (d_logit >= TAU {TAU}): {pct(s['readability_passed_rate'])}"
        + ("" if s["mean_d_logit"] is None else f"   (mean d_logit {s['mean_d_logit']:+.2f})"),
        f"passed (equivalent AND readability rose): {pct(s['passed_rate'])}",
        f"informational: easy (level <= {EASY_LEVEL_CEILING}): {pct(s['easy_rate'])}   "
        f"predicted level distribution: {dict(sorted(s['level_distribution'].items()))}",
    ]
    return "\n".join(lines)


def load_pairs(path: Path) -> pl.DataFrame:
    suffix = path.suffix.lower()
    if suffix in (".jsonl", ".ndjson"):
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        for row in rows:  # nested values (dicts/lists) are stringified: keeps the schema flat and safe
            for k, v in row.items():
                if isinstance(v, (dict, list)):
                    row[k] = json.dumps(v, ensure_ascii=False)
        return pl.DataFrame(rows, infer_schema_length=None)
    if suffix == ".csv":
        return pl.read_csv(path, encoding="utf8-lossy")
    if suffix == ".parquet":
        return pl.read_parquet(path)
    raise ValueError(f"unsupported input type {suffix!r}: use .jsonl, .csv or .parquet")


def main() -> None:
    parser = argparse.ArgumentParser(description="Score (original, simplified) pairs with the project's validators.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, default=None, help="default: data/processed/<input>_validated.parquet")
    parser.add_argument("--original-col", default="original_text")
    parser.add_argument("--simplified-col", default="simplified_text")
    parser.add_argument("--limit", type=int, default=0, help="score a seeded random sample of N pairs (cheap test)")
    parser.add_argument("--workers", type=int, default=8, help="parallel equivalence API calls")
    parser.add_argument("--skip-equivalence", action="store_true", help="readability check only: local, no API calls")
    parser.add_argument("--skip-readability", action="store_true", help="equivalence check only")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto",
                        help="readability model: GPU (torch) or CPU (cached ONNX); auto picks the GPU if there is one")
    parser.add_argument("--tau", type=float, default=TAU, help="readability gate: minimum rise in logit P(easy)")
    args = parser.parse_args()

    df = load_pairs(args.input)
    for col in (args.original_col, args.simplified_col):
        if col not in df.columns:
            raise SystemExit(f"column {col!r} not found in {args.input}; columns: {df.columns}")
    if args.limit and args.limit < df.height:
        df = df.sample(n=args.limit, seed=0)
    out_path = args.out or PROCESSED_DIR / f"{args.input.stem}_validated.parquet"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"{df.height} pairs from {args.input}")

    readability = None if args.skip_readability else load_readability_classifier(args.device)
    validator = None if args.skip_equivalence else load_equivalence_validator()
    scored = validate_pairs(
        df[args.original_col].to_list(), df[args.simplified_col].to_list(), validator, readability,
        workers=args.workers, checkpoint_path=out_path.with_suffix(".checkpoint.jsonl") if validator else None,
        tau=args.tau,
    )
    result = df.hstack(scored)
    result.write_parquet(out_path)
    print(f"\nsaved {out_path}\n\n{format_summary(summarize(scored))}")


if __name__ == "__main__":
    main()
