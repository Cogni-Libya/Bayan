"""Confidence-gated decoding: greedy everywhere, beam search only on the sentences the model is least sure of.

  python hybrid_conf.py --data bench_data --split dev --model PATH --prefix "بسط: " --out out_h/ [--beams 4]

Per app piece (sentence of 6+ words): greedy output with its confidence (mean and minimum token log-probability)
and the beam output. Then, for each share q in --shares, the q least-confident pieces (by mean log-probability,
ranked within the split) take the beam output, the rest keep greedy; the per-sentence safety net (numbers, Latin
tokens, negation / limit / condition flags) applies after, and the app's guards assemble the item.
Writes OUT/SPLIT__PREFIXhyb{q}.jsonl for every share, OUT/SPLIT__pieces.jsonl (per-piece detail) and the share of
pieces routed to beam.
"""
import argparse, json
from collections import Counter
from pathlib import Path
import re

import torch
from transformers import AutoModelForSeq2SeqLM, T5Tokenizer
from bayanbench.text import assemble, numbers, pieces
from bayanbench.measures import flags

LATIN = re.compile(r"[A-Za-z][A-Za-z0-9\-\.]*")
ap = argparse.ArgumentParser()
ap.add_argument("--data", required=True); ap.add_argument("--split", required=True); ap.add_argument("--model", required=True)
ap.add_argument("--prefix", required=True); ap.add_argument("--out", required=True); ap.add_argument("--name", default="model3")
ap.add_argument("--beams", type=int, default=4); ap.add_argument("--bs", type=int, default=24)
ap.add_argument("--shares", default="0,0.1,0.2,0.3,0.5,1")
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
tok = T5Tokenizer.from_pretrained(a.model, legacy=True)
model = AutoModelForSeq2SeqLM.from_pretrained(a.model).cuda().eval()
items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(a.data) / "items" / f"{a.split}.jsonl", encoding="utf-8")}
ids = list(items)
todo = [(k, s) for k, i in enumerate(ids) for _, s, m in pieces(items[i]["source"]) if m]
order = sorted(range(len(todo)), key=lambda j: len(todo[j][1]))
G, B, conf = [None] * len(todo), [None] * len(todo), [None] * len(todo)
with torch.no_grad():
    for b in range(0, len(order), a.bs):
        idx = order[b:b + a.bs]
        enc = tok([a.prefix + todo[j][1] for j in idx], max_length=256, truncation=True, padding=True, return_tensors="pt").to("cuda")
        g = model.generate(**enc, max_length=256, num_beams=1, do_sample=False, no_repeat_ngram_size=3,
                           output_scores=True, return_dict_in_generate=True)
        ts = model.compute_transition_scores(g.sequences, g.scores, normalize_logits=True)   # log-prob of each chosen token
        mask = g.sequences[:, 1:] != tok.pad_token_id
        for row, j in enumerate(idx):
            lp = ts[row][mask[row]].float()
            conf[j] = (float(lp.mean()) if len(lp) else 0.0, float(lp.min()) if len(lp) else 0.0)
        for j, t in zip(idx, tok.batch_decode(g.sequences, skip_special_tokens=True)): G[j] = t.strip()
        bb = model.generate(**enc, max_length=256, num_beams=a.beams, do_sample=False, no_repeat_ngram_size=3)
        for j, t in zip(idx, tok.batch_decode(bb, skip_special_tokens=True)): B[j] = t.strip()
        if (b // a.bs) % 20 == 0: print(f"{b + len(idx)}/{len(todo)} pieces", flush=True)


def unsafe(src, o):
    ns, no = Counter(numbers(src)), Counter(numbers(o))
    if any(no[x] < c for x, c in ns.items()): return True
    ls, lo = Counter(LATIN.findall(src)), Counter(LATIN.findall(o))
    if any(lo[x] < c for x, c in ls.items()): return True
    return any(v for v in flags(src, o).values())


with open(out / f"{a.split}__pieces.jsonl", "w", encoding="utf-8") as f:
    for (k, s), g_, b_, c in zip(todo, G, B, conf):
        f.write(json.dumps({"item": ids[k], "source": s, "greedy": g_, "beam": b_, "mean_lp": c[0], "min_lp": c[1]}, ensure_ascii=False) + "\n")
rank = sorted(range(len(todo)), key=lambda j: conf[j][0])            # least confident first
for q in [float(x) for x in a.shares.split(",")]:
    use_beam = set(rank[:round(q * len(todo))])
    per = [[] for _ in ids]
    for j, (k, s) in enumerate(todo):
        o = B[j] if j in use_beam else G[j]
        per[k].append(s if unsafe(s, o) else o)
    with open(out / f"{a.split}__{a.name}-hyb{int(100 * q)}.jsonl", "w", encoding="utf-8") as f:
        for i, o in zip(ids, per):
            f.write(json.dumps({"id": i, "output": assemble(items[i]["source"], o, guards=True)}, ensure_ascii=False) + "\n")
    print(f"share {q:.2f}: {len(use_beam)}/{len(todo)} pieces with beam", flush=True)
print("HYBRID_GEN_DONE", flush=True)
