"""Bench outputs the way the app makes them, plain and with a per-sentence safety net, from a PyTorch or ONNX model.

  python predict_net.py --data bench_data --split dev --model PATH --prefix "بسط: " --backend hf|ort --out-plain a.jsonl --out-net b.jsonl

Same pipeline as `bayanbench predict`: the selection is split into the app's pieces (sentences of 6+ words go to the
model), greedy decoding, 256 tokens, no repeated 3-grams, then the app's guards (retention fallback, punctuation fix).
Safety net, per piece: if the model's piece drops a number or a Latin token, or changes the count of negation, limit
or condition words (BayanBench's flags), that piece is shown unchanged. The plain file has no net.
--backend ort loads an ONNX export (optimum ORTModelForSeq2SeqLM, e.g. the int8 one from onnx_export.py).
"""
import argparse, json, re, time
from collections import Counter
from pathlib import Path

from bayanbench.text import assemble, numbers, pieces
from bayanbench.measures import flags

LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]*")

ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True)
ap.add_argument("--split", required=True)
ap.add_argument("--model", required=True)
ap.add_argument("--prefix", required=True)
ap.add_argument("--backend", default="hf", choices=["hf", "ort"])
ap.add_argument("--out-plain", required=True)
ap.add_argument("--out-net", required=True)
ap.add_argument("--bs", type=int, default=24)
ap.add_argument("--device", default=None)
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--num-beams", type=int, default=1)
a = ap.parse_args()

import torch
from transformers import AutoConfig, AutoTokenizer, T5Tokenizer
cfg = AutoConfig.from_pretrained(a.model)
tok = T5Tokenizer.from_pretrained(a.model, legacy=True) if cfg.model_type in ("t5", "mt5") else AutoTokenizer.from_pretrained(a.model)
if a.backend == "ort":
    try:
        from optimum.onnxruntime import ORTModelForSeq2SeqLM
    except ImportError:
        from optimum.onnxruntime.modeling_seq2seq import ORTModelForSeq2SeqLM
    model = ORTModelForSeq2SeqLM.from_pretrained(a.model, use_cache=True); dev = "cpu"
else:
    from transformers import AutoModelForSeq2SeqLM
    dev = a.device or ("cuda" if torch.cuda.is_available() else "cpu")
    model = AutoModelForSeq2SeqLM.from_pretrained(a.model).to(dev).eval()

items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(a.data) / "items" / f"{a.split}.jsonl", encoding="utf-8")}
ids = list(items)[:a.limit] if a.limit else list(items)
todo = [(k, s) for k, i in enumerate(ids) for _, s, to_model in pieces(items[i]["source"]) if to_model]
order = sorted(range(len(todo)), key=lambda j: len(todo[j][1]))
outs, t0 = [None] * len(todo), time.time()
with torch.no_grad():
    for b in range(0, len(order), a.bs):
        idx = order[b:b + a.bs]
        enc = tok([a.prefix + todo[j][1] for j in idx], max_length=256, truncation=True, padding=True, return_tensors="pt")
        if dev != "cpu": enc = enc.to(dev)
        g = model.generate(**enc, max_length=256, num_beams=a.num_beams, do_sample=False, no_repeat_ngram_size=3)
        for j, t in zip(idx, tok.batch_decode(g, skip_special_tokens=True)):
            outs[j] = t.strip()
        if (b // a.bs) % 10 == 0: print(f"{b + len(idx)}/{len(todo)} pieces [{time.time() - t0:.0f}s]", flush=True)


def unsafe(src, out):
    no = Counter(numbers(out))
    if any(no[x] < c for x, c in Counter(numbers(src)).items()): return True
    ls, lo = Counter(LATIN.findall(src)), Counter(LATIN.findall(out))
    if any(lo[x] < c for x, c in ls.items()): return True
    return any(v for v in flags(src, out).values())


per = [[] for _ in ids]; per_net = [[] for _ in ids]; blocked = 0
for (k, s), o in zip(todo, outs):
    per[k].append(o)
    bad = unsafe(s, o); blocked += bad
    per_net[k].append(s if bad else o)
with open(a.out_plain, "w", encoding="utf-8") as f1, open(a.out_net, "w", encoding="utf-8") as f2:
    for i, o, on in zip(ids, per, per_net):
        f1.write(json.dumps({"id": i, "output": assemble(items[i]["source"], o, guards=True)}, ensure_ascii=False) + "\n")
        f2.write(json.dumps({"id": i, "output": assemble(items[i]["source"], on, guards=True)}, ensure_ascii=False) + "\n")
print(f"wrote {len(ids)} items; safety net blocked {blocked}/{len(todo)} pieces ({100 * blocked / max(1, len(todo)):.1f}%) [{time.time() - t0:.0f}s]", flush=True)
