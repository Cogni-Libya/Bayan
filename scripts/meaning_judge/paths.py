"""Shared locations. Override with environment variables; nothing here depends on a particular machine.

  MEANING_BENCH_DIR   bench.jsonl, per-scorer results, teacher labels     (default data/processed/meaning_bench)
  VERIFIER_DATA_DIR   train.jsonl / val.jsonl / jev_labels.jsonl          (default <MEANING_BENCH_DIR>/verifier_data)
"""
import os
from pathlib import Path

BENCH_DIR = Path(os.environ.get("MEANING_BENCH_DIR", "data/processed/meaning_bench"))
BENCH = BENCH_DIR / "bench.jsonl"
VERIFIER_DATA = Path(os.environ.get("VERIFIER_DATA_DIR", BENCH_DIR / "verifier_data"))


def _norm(t):
    import re
    return re.sub(r"\s+", " ", re.sub(r"[ً-ْٰـ]", "", t)).strip()


def leaked_sources():
    """Training sources whose text is also a bench original (cached in BENCH_DIR/leak_sources.json)."""
    import json
    f = BENCH_DIR / "leak_sources.json"
    if f.exists():
        return set(json.load(open(f, encoding="utf-8")))
    bench = {_norm(json.loads(l)["original"]) for l in open(BENCH, encoding="utf-8")}
    leak = sorted({json.loads(l)["src"] for sp in ("train", "val") for l in open(VERIFIER_DATA / f"{sp}.jsonl", encoding="utf-8")
                   if _norm(json.loads(l)["src"]) in bench})
    json.dump(leak, open(f, "w", encoding="utf-8"), ensure_ascii=False)
    return set(leak)


def load_split(name, data_dir=None):
    """train / val rows with every bench-leaked source removed (done BEFORE any seeded sampling, as in the runs)."""
    import json
    d = Path(data_dir) if data_dir else VERIFIER_DATA
    leak = leaked_sources()
    return [r for r in (json.loads(l) for l in open(d / f"{name}.jsonl", encoding="utf-8")) if r["src"] not in leak]
