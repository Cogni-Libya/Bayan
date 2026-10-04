"""Candidates for student DPO: greedy output + N top-p samples per corpus-v1 source, from the trained student.

  python dpo_sample.py --model Congi-libya/bayan-arat5-v1 --data v1/train.jsonl --out cands.jsonl --n 8

Runs under transformers 4.x (AraT5's slow tokenizer, tied weights). One line per source:
{"id", "candidates": [greedy, sample_1, ..., sample_N]} (duplicates kept; the scorer deduplicates).
"""
import argparse, json, time

import torch
from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer, T5Tokenizer

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--data", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--prefix", default="بسط: ")
ap.add_argument("--n", type=int, default=8)
ap.add_argument("--top-p", type=float, default=0.95)
ap.add_argument("--temperature", type=float, default=1.0)
ap.add_argument("--bs", type=int, default=32, help="sources per batch")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
ap.add_argument("--seed", type=int, default=0)
a = ap.parse_args()
torch.manual_seed(a.seed)

cfg = AutoConfig.from_pretrained(a.model)
tok = T5Tokenizer.from_pretrained(a.model, legacy=True) if cfg.model_type in ("t5", "mt5") else AutoTokenizer.from_pretrained(a.model)
model = AutoModelForSeq2SeqLM.from_pretrained(a.model).to(a.device).eval()
rows = [json.loads(l) for l in open(a.data, encoding="utf-8")]
if a.limit: rows = rows[:a.limit]
order = sorted(range(len(rows)), key=lambda i: len(rows[i]["source"]))
pre = a.prefix.strip()


def dec(g):
    out = [t.strip() for t in tok.batch_decode(g, skip_special_tokens=True)]
    return [t[len(pre):].strip() if pre and t.startswith(pre) else t for t in out]


res, t0 = [None] * len(rows), time.time()
with torch.no_grad():
    for k in range(0, len(order), a.bs):
        b = order[k:k + a.bs]
        enc = tok([a.prefix + rows[i]["source"] for i in b], max_length=256, truncation=True, padding=True,
                  return_tensors="pt").to(a.device)
        greedy = dec(model.generate(**enc, max_length=256, num_beams=1, do_sample=False, no_repeat_ngram_size=4))
        samp = dec(model.generate(**enc, max_length=256, do_sample=True, top_p=a.top_p, temperature=a.temperature,
                                  num_return_sequences=a.n, no_repeat_ngram_size=4))
        for j, i in enumerate(b):
            res[i] = [greedy[j]] + samp[j * a.n:(j + 1) * a.n]
        if (k // a.bs) % 20 == 0:
            print(f"{k + len(b)}/{len(rows)} sources [{time.time() - t0:.0f}s]", flush=True)
with open(a.out, "w", encoding="utf-8") as f:
    for r, c in zip(rows, res):
        f.write(json.dumps({"id": r["id"], "candidates": c}, ensure_ascii=False) + "\n")
print(f"wrote {len(rows)} sources x {a.n + 1} candidates to {a.out} [{time.time() - t0:.0f}s]", flush=True)
