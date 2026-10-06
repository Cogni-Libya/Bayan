"""Judge candidates that were never scored for meaning: the <checkpoint>.pending_judge.jsonl written by
rescore_sentencewise.py. Same compiled judge, same call shape as the pipeline (all of a source's pending
candidates in one call), resumable.

    python scripts/judge_pending.py data/processed/v1_final/barec_hard_v1_checkpoint.pending_judge.jsonl \\
        --judge-url http://localhost:8001/v1 --concurrency 48
Writes <input>.judged.jsonl: {"ID", "candidates": [{"simplified_text", "equivalence_score", "equivalence_reasoning"}]}.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: F401  (numpy before dspy)
import dspy
from tqdm import tqdm

from barec_simplification_pipeline import (
    COMPILED_EQUIVALENCE_VALIDATOR_PATH, VLLM_JUDGE_MODEL, CheckSemanticEquivalence, _vllm_lm, raise_fd_limit,
)
from validation import score_equivalence


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pending", type=Path)
    ap.add_argument("--judge-url", default="http://localhost:8001/v1")
    ap.add_argument("--judge-model", default=VLLM_JUDGE_MODEL)
    ap.add_argument("--concurrency", type=int, default=48)
    args = ap.parse_args()

    import litellm  # imported once, before the thread pool (lazy-import race otherwise)
    litellm.completion  # noqa: B018
    raise_fd_limit()
    dspy.configure(adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))
    judge = dspy.Predict(CheckSemanticEquivalence)
    if COMPILED_EQUIVALENCE_VALIDATOR_PATH.exists():
        judge.load(str(COMPILED_EQUIVALENCE_VALIDATOR_PATH))
    judge.set_lm(_vllm_lm(args.judge_model, args.judge_url, temperature=0.0, max_tokens=2048))

    out_path = args.pending.with_suffix(".judged.jsonl")
    done = {json.loads(l)["ID"] for l in open(out_path, encoding="utf-8")} if out_path.exists() else set()
    jobs = [j for j in (json.loads(l) for l in open(args.pending, encoding="utf-8")) if j["ID"] not in done]
    print(f"{len(jobs)} sources to judge ({len(done)} already done)")
    lock, failures = threading.Lock(), 0

    def work(job: dict) -> dict:
        scored = score_equivalence(judge, job["original_text"], job["candidates"])
        return {"ID": job["ID"], "judge_model": args.judge_model, "candidates": [
            {"simplified_text": t, "equivalence_score": s, "equivalence_reasoning": why}
            for t, (s, why) in zip(job["candidates"], scored)]}

    with open(out_path, "a", encoding="utf-8") as f, ThreadPoolExecutor(args.concurrency) as pool:
        futures = {pool.submit(work, j): j for j in jobs}
        for fut in tqdm(as_completed(futures), total=len(futures), desc="judging"):
            try:
                row = fut.result()
            except Exception as e:  # one malformed response skips that source; rerun to retry it
                failures += 1
                tqdm.write(f"  skipped ID {futures[fut]['ID']}: {type(e).__name__}: {str(e)[:120]}")
                continue
            with lock:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
    print(f"done; {failures} failed (rerun to retry)")


if __name__ == "__main__":
    main()
