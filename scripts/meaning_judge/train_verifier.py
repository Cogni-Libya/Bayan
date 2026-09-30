"""Train a cross-encoder meaning verifier: (source, rewrite) -> P(meaning kept), soft-label BCE.

  python train_verifier.py --model aubmindlab/bert-base-arabertv02 --out runs/arabert --labels teacher
  python train_verifier.py --model Qwen/Qwen3-0.6B --out runs/qwen06 --labels jev --lr 1e-5

--labels teacher : teacher rows use the DeepSeek/Qwen score; synthetic rows 0/1
--labels jev     : teacher rows use Jev's same_meaning (from jev_labels.jsonl, key -> score); synthetic rows 0/1
Writes: best checkpoint (by val AUC), val metrics per epoch, and test predictions (test_preds.jsonl)."""
import argparse
import json
import math
import random
import time
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import AutoModelForSequenceClassification, AutoTokenizer, get_linear_schedule_with_warmup


def read(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def auc(scores, labels):
    s = np.asarray(scores); y = np.asarray(labels).astype(bool)
    pos, neg = s[y], s[~y]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    ranks = np.empty(len(order)); ranks[order] = np.arange(1, len(order) + 1)
    allv = np.concatenate([pos, neg])
    for v in np.unique(allv):                      # average ranks for ties
        m = allv == v
        ranks[m] = ranks[m].mean()
    return (ranks[:len(pos)].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--data", default="verifier_data")
    ap.add_argument("--out", required=True)
    ap.add_argument("--labels", choices=["teacher", "jev"], default="teacher")
    ap.add_argument("--epochs", type=int, default=2)
    ap.add_argument("--lr", type=float, default=2e-5)
    ap.add_argument("--bs", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=256)
    ap.add_argument("--limit", type=int, default=0, help="smoke test: use only N training rows")
    a = ap.parse_args()
    torch.manual_seed(0); random.seed(0)
    D, out = Path(a.data), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    train, val, test = read(D / "train.jsonl"), read(D / "val.jsonl"), read(D / "test_pairs.jsonl")
    if a.labels == "jev":
        jl = {r["key"]: r["y"] for r in read(D / "jev_labels.jsonl")}
        # Jev labels every pair that is not a code-planted negative. SAMER human rewrites (and augmentations of them)
        # are NOT meaning-preserving by construction: SAMER's simplifiers generalise and swap words ("angels" ->
        # "messengers", "elated" -> "drunk"), so they take Jev's score too, not 1.0.
        for rows in (train, val):
            for r in rows:
                if r["origin"].startswith("neg_"):
                    continue
                r["y"] = jl.get(r.get("key"))   # None if Jev has no label: dropped below, teachers never mixed
        train = [r for r in train if r["y"] is not None]
        val = [r for r in val if r["y"] is not None]
    if a.limit:
        random.shuffle(train)
        train = train[:a.limit]
    print(f"train {len(train)}  val {len(val)}  test {len(test)}  labels={a.labels}", flush=True)

    tok = AutoTokenizer.from_pretrained(a.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForSequenceClassification.from_pretrained(a.model, num_labels=1, ignore_mismatched_sizes=True, torch_dtype=torch.bfloat16
                                                               if "qwen" in a.model.lower() else torch.float32)
    model.config.pad_token_id = tok.pad_token_id
    dev = "cuda"
    model.to(dev)

    def collate(batch):
        enc = tok([b["src"] for b in batch], [b["tgt"] for b in batch], truncation=True, max_length=a.max_len,
                  padding=True, return_tensors="pt")
        if "y" in batch[0]:
            enc["labels"] = torch.tensor([float(b["y"]) for b in batch])
        return enc

    tl = DataLoader(train, batch_size=a.bs, shuffle=True, collate_fn=collate, num_workers=2)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    steps = len(tl) * a.epochs
    sch = get_linear_schedule_with_warmup(opt, int(0.06 * steps), steps)
    lossf = torch.nn.BCEWithLogitsLoss()
    use_amp = model.dtype == torch.float32

    @torch.no_grad()
    def predict(rows):
        model.eval()
        out_s = []
        for i in range(0, len(rows), 128):
            b = [{"src": r["src"], "tgt": r["tgt"]} for r in rows[i:i + 128]]
            enc = collate(b).to(dev)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
                lg = model(**enc).logits.float().squeeze(-1)
            out_s += torch.sigmoid(lg).tolist()
        model.train()
        return out_s

    best, log = -1, []
    t0 = time.time()
    model.train()
    for ep in range(a.epochs):
        for it, batch in enumerate(tl):
            batch = batch.to(dev)
            y = batch.pop("labels")
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=use_amp):
                lg = model(**batch).logits.float().squeeze(-1)
            loss = lossf(lg, y)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step(); sch.step(); opt.zero_grad()
            if it % 200 == 0:
                print(f"ep {ep} it {it}/{len(tl)} loss {loss.item():.4f} [{time.time() - t0:.0f}s]", flush=True)
        ps = predict(val)
        hi_, lo_ = (0.6, 0.3) if a.labels == "jev" else (0.85, 0.5)
        m = {"epoch": ep,
             "val AUC (clear good vs clear bad)": auc(
                 [p for p, r in zip(ps, val) if r["y"] >= hi_ or r["y"] < lo_],
                 [r["y"] >= hi_ for r in val if r["y"] >= hi_ or r["y"] < lo_]),
             "val Spearman vs label": float(np.corrcoef(np.argsort(np.argsort(ps)), np.argsort(np.argsort([r["y"] for r in val])))[0, 1]),
             "val AUC synthetic neg vs pos": auc(
                 [p for p, r in zip(ps, val) if not r["origin"].startswith("teacher")],
                 [r["y"] > 0.5 for r in val if not r["origin"].startswith("teacher")]),
             "val MSE": float(np.mean([(p - r["y"]) ** 2 for p, r in zip(ps, val)]))}
        print(json.dumps(m), flush=True)
        log.append(m)
        key = m["val AUC (clear good vs clear bad)"]
        if key > best:
            best = key
            model.save_pretrained(out / "best"); tok.save_pretrained(out / "best")
            tp = predict(test)
            with open(out / "test_preds.jsonl", "w", encoding="utf-8") as f:
                for r, p in zip(test, tp):
                    f.write(json.dumps({"i": r["i"], "p": p}) + "\n")
    t = time.time()
    _ = predict(test[:256])
    json.dump({"log": log, "best_val_auc": best, "secs": time.time() - t0,
               "gpu_ms_per_pair": 1000 * (time.time() - t) / 256}, open(out / "metrics.json", "w"), indent=1)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
