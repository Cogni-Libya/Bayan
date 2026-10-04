"""Calibrate the equivalence threshold for a new judge model before trusting its scores.

The 0.7 threshold was chosen for DeepSeek; another judge's scores sit on a different scale. This scores
two labelled sets with the judge exactly as the pipeline calls it (the compiled CheckSemanticEquivalence
program, several candidates per call, tashkeel stripped), then sweeps the threshold:

  adversarial -- data/processed/equivalence_adversarial/variants.jsonl: per original, one faithful
                 rewrite and four broken ones (added claim, deleted content, negation, turned into a
                 question), all five judged in one call like a real candidate batch;
  human       -- data/processed/review/review_pairs.jsonl + annotations/*.jsonl: pipeline outputs a
                 person labelled same / minor / changed meaning.

    uv run python scripts/calibrate_judge.py --judge-url http://localhost:8001/v1 --judge-model RedHatAI/Qwen3.8-27B-INT4
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: F401  (numpy before dspy, see barec_simplification_pipeline)
import dspy
import polars as pl
from tqdm import tqdm

from barec_simplification_pipeline import (
    COMPILED_EQUIVALENCE_VALIDATOR_PATH, PROCESSED_DIR, VLLM_JUDGE_MODEL, CheckSemanticEquivalence, _vllm_lm,
)
from corpus_constraints import strip_tashkeel
from validation import score_equivalence

ADVERSARIAL = PROCESSED_DIR / "equivalence_adversarial" / "variants.jsonl"
HUMAN_PAIRS = PROCESSED_DIR / "review" / "review_pairs.jsonl"
HUMAN_LABELS = PROCESSED_DIR / "review" / "annotations"
VARIANT_ORDER = ("faithful", "add", "delete", "negate", "question")
THRESHOLDS = (0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9)


def load_jobs() -> list[dict]:
    jobs = []
    for line in open(ADVERSARIAL, encoding="utf-8"):
        r = json.loads(line)
        kinds = [k for k in VARIANT_ORDER if k in r["variants"]]
        jobs.append({"set": "adversarial", "original": r["original"], "labels": kinds,
                     "candidates": [r["variants"][k] for k in kinds]})
    labels = {}
    for f in sorted(HUMAN_LABELS.glob("*.jsonl")):
        for line in open(f, encoding="utf-8"):
            a = json.loads(line)
            labels[a["item"]] = a["meaning"]
    for line in open(HUMAN_PAIRS, encoding="utf-8"):
        r = json.loads(line)
        if r["id"] in labels:
            jobs.append({"set": "human", "original": r["original"], "labels": [labels[r["id"]]],
                         "candidates": [r["candidate"]]})
    return jobs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge-url", default="http://localhost:8001/v1")
    ap.add_argument("--judge-model", default=VLLM_JUDGE_MODEL)
    ap.add_argument("--concurrency", type=int, default=32)
    ap.add_argument("--out", type=Path, default=PROCESSED_DIR / "judge_calibration.parquet")
    args = ap.parse_args()

    dspy.configure(adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))
    judge = dspy.Predict(CheckSemanticEquivalence)
    if COMPILED_EQUIVALENCE_VALIDATOR_PATH.exists():
        judge.load(str(COMPILED_EQUIVALENCE_VALIDATOR_PATH))
    judge.set_lm(_vllm_lm(args.judge_model, args.judge_url, temperature=0.0, max_tokens=2048))

    jobs = load_jobs()

    def work(job: dict) -> list[dict]:
        orig = strip_tashkeel(job["original"])
        cands = [strip_tashkeel(c) for c in job["candidates"]]
        try:
            scored = score_equivalence(judge, orig, cands)
        except Exception as e:  # a parse failure drops this job, it doesn't stop the calibration
            print(f"  failed: {type(e).__name__}: {str(e)[:120]}")
            return []
        return [{"set": job["set"], "label": lab, "score": s, "original": orig, "candidate": c}
                for lab, c, (s, _) in zip(job["labels"], cands, scored)]

    with ThreadPoolExecutor(args.concurrency) as pool:
        rows = [r for out in tqdm(pool.map(work, jobs), total=len(jobs), desc="judging") for r in out]
    df = pl.DataFrame(rows)
    df.write_parquet(args.out)

    print(f"\n{df.height} judged pairs ({args.judge_model}); accept rate = share with score >= threshold")
    groups = [("adversarial", k) for k in VARIANT_ORDER] + [("human", k) for k in ("same", "minor", "changed")]
    print("thr   " + " ".join(f"{s[:3]}:{k:<8}" for s, k in groups))
    for t in THRESHOLDS:
        cells = []
        for s, k in groups:
            g = df.filter((pl.col("set") == s) & (pl.col("label") == k))
            cells.append(f"{(g['score'] >= t).mean():>12.0%}" if g.height else f"{'-':>12}")
        print(f"{t:<5} " + " ".join(cells))
    print("\nDeepSeek at 0.7 (references/04_dataset_construction): accepted 34% of additions, 25% of deletions.")


if __name__ == "__main__":
    main()
