"""Find protected text that BAREC's Source tag doesn't mark: classical Arabic verse inside prose books and
curricula, and Quran / hadith quoted without a marker (verse numbers only, or none). Such sources are
copied unchanged (identity pairs) instead of being simplified.

Validated on BAREC rows whose Source already gives the answer (Hanging Odes = classical poetry, Quran,
Hadith, and prose-only sources) before its labels are used.

    python scripts/classify_protected.py --judge-url http://localhost:8001/v1          # validate, then classify
Writes data/processed/protected_labels.jsonl: {"ID", "kind"} for every non-test hard-route source.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Literal

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np  # noqa: F401  (numpy before dspy)
import dspy
import polars as pl
from tqdm import tqdm

from barec_simplification_pipeline import (
    PROCESSED_DIR, VLLM_JUDGE_MODEL, _vllm_lm, load_and_clean_barec, raise_fd_limit,
)

KIND = Literal["prose", "classical_poetry", "quran", "hadith"]
PROTECTED_KINDS = ("classical_poetry", "quran", "hadith")
OUT = PROCESSED_DIR / "protected_labels.jsonl"
PROSE_SOURCES = ("Wikipedia", "WikiNews", "Majed", "Constitutions", "ArabicMMLU")


class ClassifyTextKind(dspy.Signature):
    """Classify one line of Arabic text by what it IS, not what it is about.
    - classical_poetry: a line or half-line of classical (pre-modern, metered, rhymed) Arabic verse
      (بيت أو شطر من الشعر العربي القديم), wherever it appears.
    - quran: the text of a Quran verse itself (it may carry verse numbers like ١٠٣).
    - hadith: the words of a hadith of the Prophet itself.
    - prose: everything else -- including prose that talks ABOUT a verse, a hadith or a poem, explains
      one, or introduces it, modern free verse, songs, quiz questions and instructions."""

    text: str = dspy.InputField()
    kind: KIND = dspy.OutputField()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--judge-url", default="http://localhost:8001/v1")
    ap.add_argument("--judge-model", default=VLLM_JUDGE_MODEL)
    ap.add_argument("--concurrency", type=int, default=64)
    ap.add_argument("--validate-only", action="store_true")
    ap.add_argument("--skip-validation", action="store_true")
    ap.add_argument("--ids", type=Path, help="classify only these source IDs (one per line); default: every hard-route source")
    args = ap.parse_args()

    import litellm  # imported once, before the thread pool
    litellm.completion  # noqa: B018
    raise_fd_limit()
    dspy.configure(adapter=dspy.ChatAdapter(use_json_adapter_fallback=False))
    clf = dspy.Predict(ClassifyTextKind)
    clf.set_lm(_vllm_lm(args.judge_model, args.judge_url, temperature=0.0, max_tokens=32))

    def run(items: list[tuple[int, str]], desc: str) -> dict[int, str]:
        out = {}
        with ThreadPoolExecutor(args.concurrency) as pool:
            futs = {pool.submit(lambda t: clf(text=t).kind, text): i for i, text in items}
            for f in tqdm(as_completed(futs), total=len(futs), desc=desc):
                try:
                    out[futs[f]] = f.result()
                except Exception:
                    out[futs[f]] = "error"
        return out

    barec = load_and_clean_barec().filter(pl.col("barec_split") != "test")
    if not args.skip_validation:
        random.seed(0)
        truth = {"Hanging Odes": "classical_poetry", "Quran": "quran", "Hadith": "hadith"}
        val = []
        for src, kind in truth.items():
            rows = barec.filter(pl.col("Source") == src).sample(n=100, seed=0)
            val += [(r["ID"], r["Sentence"], kind) for r in rows.iter_rows(named=True)]
        prose = barec.filter(pl.col("Source").is_in(PROSE_SOURCES) & (pl.col("route") == "hard")).sample(n=300, seed=0)
        val += [(r["ID"], r["Sentence"], "prose") for r in prose.iter_rows(named=True)]
        pred = run([(i, t) for i, t, _ in val], "validating")
        print("\nvalidation (rows / predicted as):")
        for kind in ("classical_poetry", "quran", "hadith", "prose"):
            rows = [pred[i] for i, _, k in val if k == kind]
            dist = {p: rows.count(p) for p in sorted(set(rows))}
            print(f"  true {kind:<17} n={len(rows):3}  {dist}")
        fp = sum(1 for i, _, k in val if k == "prose" and pred[i] in PROTECTED_KINDS)
        print(f"  prose wrongly protected: {fp}/300")
    if args.validate_only:
        return

    hard = barec.filter(pl.col("route") == "hard")
    if args.ids:
        wanted = {int(x) for x in args.ids.read_text().split()}
        hard = hard.filter(pl.col("ID").is_in(wanted))
    labels = run([(r["ID"], r["Sentence"]) for r in hard.iter_rows(named=True)], "classifying")
    with open(OUT, "w", encoding="utf-8") as f:
        for i, k in labels.items():
            f.write(json.dumps({"ID": i, "kind": k}) + "\n")
    counts = {k: sum(1 for v in labels.values() if v == k) for k in set(labels.values())}
    print(f"wrote {len(labels)} labels to {OUT}: {counts}")


if __name__ == "__main__":
    main()
