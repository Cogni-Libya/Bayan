"""Re-score every candidate in a generation checkpoint with hardest-sentence readability, locally.

readability_lead_sentence = E[level](source, scored whole -- it is one BAREC sentence)
                            - max over the rewrite's sentences of E[level](sentence)
with MCQ items scored on the question stem only (corpus_constraints.readability_units). Candidates that
now reach MIN_READABILITY_LEAD but were never judged (the pipeline skipped the judge below the old
whole-text floor) are listed for judge_pending.py.

    uv run python scripts/rescore_sentencewise.py data/processed/v1_final/barec_hard_v1_checkpoint.jsonl
Writes <checkpoint>.sentencewise.jsonl (one row per source: ID + per-candidate lead_sentence) and
<checkpoint>.pending_judge.jsonl (sources with unjudged candidates at or above the floor).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: F401  (numpy before dspy-importing modules)

from barec_simplification_pipeline import MIN_READABILITY_LEAD
from camel_readability import CamelReadability
from corpus_constraints import mcq_stem, readability_units


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkpoint", type=Path)
    ap.add_argument("--batch-size", type=int, default=32)
    args = ap.parse_args()

    rows = [json.loads(l) for l in open(args.checkpoint, encoding="utf-8") if l.strip()]
    texts = set()
    for r in rows:
        texts.add(mcq_stem(r["original_text"]))
        for c in (r.get("all_candidates") or []) + (r.get("below_lead") or []):
            texts.update(readability_units(c["simplified_text"]))
    texts = sorted(texts)
    print(f"{len(rows)} sources, {len(texts)} distinct texts to score")
    cam = CamelReadability()
    level = dict(zip(texts, cam.expected_level(cam.predict_probs(texts, batch_size=args.batch_size, show_progress=True))))

    out = args.checkpoint.with_suffix(".sentencewise.jsonl")
    pending_path = args.checkpoint.with_suffix(".pending_judge.jsonl")
    n_pending = 0
    with open(out, "w", encoding="utf-8") as fo, open(pending_path, "w", encoding="utf-8") as fp:
        for r in rows:
            src_level = float(level[mcq_stem(r["original_text"])])
            scored = []
            for c in (r.get("all_candidates") or []) + (r.get("below_lead") or []):
                hardest = max(float(level[u]) for u in readability_units(c["simplified_text"]))
                scored.append({"simplified_text": c["simplified_text"], "source_level_stem": src_level,
                               "hardest_sentence_level": hardest, "readability_lead_sentence": src_level - hardest,
                               "equivalence_score": c.get("equivalence_score"),
                               "equivalence_reasoning": c.get("equivalence_reasoning")})
            fo.write(json.dumps({"ID": r["ID"], "candidates": scored}, ensure_ascii=False) + "\n")
            todo = [c["simplified_text"] for c in scored
                    if c["equivalence_score"] is None and c["readability_lead_sentence"] >= MIN_READABILITY_LEAD]
            if todo:
                n_pending += 1
                fp.write(json.dumps({"ID": r["ID"], "original_text": r["original_text"], "candidates": todo},
                                    ensure_ascii=False) + "\n")
    print(f"wrote {out}; {n_pending} sources have unjudged candidates at lead_sentence >= {MIN_READABILITY_LEAD} -> {pending_path}")


if __name__ == "__main__":
    main()
