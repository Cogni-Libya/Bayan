"""Score bench.jsonl with a fine-tuned 1-logit cross-encoder, both input orders.

  python score_ce.py runs/mdeberta/best ft_mdeberta.jsonl
"""
import json, sys, time
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from paths import BENCH, BENCH_DIR, VERIFIER_DATA

path, out = sys.argv[1], Path(sys.argv[2])
rows = [json.loads(l) for l in open(BENCH, encoding="utf-8")]
tok = AutoTokenizer.from_pretrained(path)
m = AutoModelForSequenceClassification.from_pretrained(path).cuda().eval()


@torch.no_grad()
def score(a, b, bs=64):
    res = []
    for k in range(0, len(a), bs):
        enc = tok(a[k:k + bs], b[k:k + bs], truncation=True, max_length=256, padding=True, return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            res += torch.sigmoid(m(**enc).logits[:, 0].float()).tolist()
    return res


t = time.time()
fwd = score([r["original"] for r in rows], [r["candidate"] for r in rows])
bwd = score([r["candidate"] for r in rows], [r["original"] for r in rows])
sec = time.time() - t
with open(out, "w") as f:
    for r, x, y in zip(rows, fwd, bwd):
        f.write(json.dumps({"id": r["id"], "fwd": x, "bwd": y}) + "\n")
json.dump({"model": f"{path} (fine-tuned)", "mode": "ce-ft", "pairs_per_sec": len(rows) / sec},
          open(str(out) + ".meta.json", "w"), indent=1)
print(f"{len(rows)} pairs, {len(rows) / sec:.0f} pairs/s (both orders)\nEXIT=0")
