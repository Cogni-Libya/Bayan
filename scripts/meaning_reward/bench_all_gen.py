"""Generate every model's outputs on reference-based test sets, and time it on CPU, for the all-models comparison.

  python bench_all_gen.py --models models.json --sets sets.json --out gen/ [--latency-n 100]

models.json: {name: {"path": local dir or HF id, "prefix": "بسط: "}}   (transformers 4.x)
sets.json:   {set: path}, each a jsonl of {"id", "source", ...}
Writes gen/<set>__<model>.jsonl ({"id", "prediction"}): whole input, greedy, max 256, no repeated 4-grams (as
model 2's train.py and dpo_train.py). Then gen/latency.json: parameters, fp32 size, seconds per sentence at batch 1 on
CPU with 4 threads over the first --latency-n sources of the first set.
"""
import argparse, json, os, time
from pathlib import Path

import torch
from transformers import AutoConfig, AutoModelForSeq2SeqLM, AutoTokenizer, T5Tokenizer

ap = argparse.ArgumentParser()
ap.add_argument("--models", required=True)
ap.add_argument("--sets", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--bs", type=int, default=48)
ap.add_argument("--latency-n", type=int, default=100)
ap.add_argument("--latency-threads", type=int, default=4)
a = ap.parse_args()
models = json.load(open(a.models, encoding="utf-8")); sets = json.load(open(a.sets, encoding="utf-8"))
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
dev = "cuda" if torch.cuda.is_available() else "cpu"


def load(spec):
    cfg = AutoConfig.from_pretrained(spec["path"])
    tok = T5Tokenizer.from_pretrained(spec["path"], legacy=True) if cfg.model_type in ("t5", "mt5") else AutoTokenizer.from_pretrained(spec["path"])
    return tok, AutoModelForSeq2SeqLM.from_pretrained(spec["path"], dtype=torch.float32)


def run(tok, model, prefix, texts, device, bs):
    pre = prefix.strip(); order = sorted(range(len(texts)), key=lambda i: len(texts[i])); res = [None] * len(texts)
    with torch.no_grad():
        for k in range(0, len(order), bs):
            b = order[k:k + bs]
            enc = tok([prefix + texts[i] for i in b], max_length=256, truncation=True, padding=True, return_tensors="pt").to(device)
            g = model.generate(**enc, max_length=256, num_beams=1, do_sample=False, no_repeat_ngram_size=4)
            for i, t in zip(b, tok.batch_decode(g, skip_special_tokens=True)):
                t = t.strip(); res[i] = t[len(pre):].strip() if pre and t.startswith(pre) else t
    return res


rows = {s: [json.loads(l) for l in open(p, encoding="utf-8")] for s, p in sets.items()}
lat = {}
for name, spec in models.items():
    t0 = time.time(); tok, model = load(spec); model.to(dev).eval()
    for s, rs in rows.items():
        f = out / f"{s}__{name}.jsonl"
        if f.exists(): continue
        preds = run(tok, model, spec["prefix"], [r["source"] for r in rs], dev, a.bs)
        with open(f, "w", encoding="utf-8") as fh:
            for r, p in zip(rs, preds): fh.write(json.dumps({"id": r["id"], "prediction": p}, ensure_ascii=False) + "\n")
        print(f"{name} {s}: {len(rs)} rows [{time.time() - t0:.0f}s]", flush=True)
    # CPU latency, batch 1, fp32
    torch.set_num_threads(a.latency_threads); model.to("cpu")
    first = next(iter(rows.values()))[:a.latency_n]
    run(tok, model, spec["prefix"], [first[0]["source"]], "cpu", 1)                       # warm-up
    t1 = time.time(); run(tok, model, spec["prefix"], [r["source"] for r in first], "cpu", 1); dt = time.time() - t1
    n_par = sum(p.numel() for p in model.parameters())
    lat[name] = {"params_M": round(n_par / 1e6, 1), "fp32_MB": round(n_par * 4 / 1e6), "cpu_s_per_sentence": round(dt / len(first), 3),
                 "cpu_threads": a.latency_threads, "n": len(first)}
    print(name, json.dumps(lat[name]), flush=True)
    del model; torch.cuda.empty_cache() if dev == "cuda" else None
json.dump(lat, open(out / "latency.json", "w"), indent=1)
print("GEN_ALL_DONE", flush=True)
