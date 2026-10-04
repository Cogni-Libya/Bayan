"""Download corpus v1 (Congi-libya/bayan-simplification-corpus, public, CC BY-SA 4.0) and write the training files.

  python prepare_v1.py --out data/processed/meaning_reward/v1

Writes train.jsonl / dev.jsonl / test.jsonl with: id, source, target, pair_type (generated / identity / protected /
short). Corpus v1 is used exactly as published: its 70/30 generated vs identity-type mix is the intended training mix,
and every generated pair already passed meaning >= 0.85 (tier A) and a >= 2 CAMeL-level readability lead.
test.jsonl is written for later, locked evaluation only; nothing here reads it.
"""
import argparse, json
from collections import Counter
from pathlib import Path

from huggingface_hub import hf_hub_download

REPO = "Congi-libya/bayan-simplification-corpus"
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="data/processed/meaning_reward/v1")
ap.add_argument("--revision", default="v1", help="dataset tag; v1 = Gemma 4 generator + Qwen3.8 judge")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)

for split in ("train", "dev", "test"):
    path = hf_hub_download(REPO, f"synthetic_{split}.jsonl", repo_type="dataset", revision=a.revision)
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    with open(out / f"{split}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["ID"], "source": r["original_text"], "target": r["simplified_text"],
                                "pair_type": r["pair_type"]}, ensure_ascii=False) + "\n")
    print(split, len(rows), dict(Counter(r["pair_type"] for r in rows)))
