"""Score several simplifiers on the same corpus-v1 split with the same reward, for a like-for-like comparison.

  python eval_models.py --split dev --out compare_dev.json \
      --model "v1-mle=runs/v1-mle/best|بسط: |" --model "v0.2-fast=Congi-libya/BayanSimplify-v0.2-Fast|بسط: |[S2] "

Each --model is NAME=PATH|PREFIX|TAG: the input is PREFIX + TAG + source, as that model was trained.
Reported per model: dev reward on generated rows and per keep-type, exact-copy rate on keep-type rows, SARI on
generated rows, judge P(same) mean, share >= 2 CAMeL levels easier, gate pass rate, copy rate on hard rows.
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "training" / "model2"))
from reward import JudgeClient, MeaningSimplicityReward, KEEP_TYPES  # noqa: E402
from sari import sari_sentence  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="data/processed/meaning_reward/v1")
ap.add_argument("--split", default="dev")
ap.add_argument("--model", action="append", required=True)
ap.add_argument("--judge-url", default="http://localhost:8001")
ap.add_argument("--judge-model", default="Congi-libya/bayan-meaning-judge-e2b")
ap.add_argument("--out", required=True)
a = ap.parse_args()
rows = [json.loads(l) for l in open(Path(a.data) / f"{a.split}.jsonl", encoding="utf-8")]
reward = MeaningSimplicityReward(JudgeClient(a.judge_url, a.judge_model), device="cuda")
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, T5Tokenizer

results = {}
for spec in a.model:
    name, rest = spec.split("=", 1); path, prefix, tag = rest.split("|")
    t0 = time.time()
    is_t5 = "t5" in path.lower()
    tok = T5Tokenizer.from_pretrained(path, legacy=True) if is_t5 else AutoTokenizer.from_pretrained(path)
    model = AutoModelForSeq2SeqLM.from_pretrained(path).cuda().eval()
    probe = tok("a")["input_ids"]; add = not (probe and probe[-1] == tok.eos_token_id)   # transformers 5.x Barthez
    def ids(texts):
        x = tok(texts, add_special_tokens=not add, truncation=True, max_length=254)["input_ids"]
        return [[tok.bos_token_id] + i + [tok.eos_token_id] for i in x] if add else x
    preds = []
    order = sorted(range(len(rows)), key=lambda i: len(rows[i]["source"]))
    out = [None] * len(rows)
    with torch.no_grad():
        for k in range(0, len(order), 64):
            b = order[k:k + 64]; x = ids([prefix + tag + rows[i]["source"] for i in b]); L = max(map(len, x))
            inp = torch.tensor([s + [tok.pad_token_id] * (L - len(s)) for s in x]).cuda()
            att = torch.tensor([[1] * len(s) + [0] * (L - len(s)) for s in x]).cuda()
            with torch.autocast("cuda", dtype=torch.bfloat16):
                g = model.generate(input_ids=inp, attention_mask=att, max_length=256, num_beams=1, do_sample=False,
                                   no_repeat_ngram_size=4)
            for i, t in zip(b, tok.batch_decode(g, skip_special_tokens=True)):
                t = t.strip(); pre = prefix.strip()
                t = t[len(pre):].strip() if pre and t.startswith(pre) else t
                out[i] = t[len(tag.strip()):].strip() if tag.strip() and t.startswith(tag.strip()) else t
    rw, info = reward([r["source"] for r in rows], out, [r["pair_type"] for r in rows])
    gi = [i for i, r in enumerate(rows) if r["pair_type"] not in KEEP_TYPES]
    ki = [i for i, r in enumerate(rows) if r["pair_type"] in KEEP_TYPES]
    res = {"reward_generated": float(rw[gi].mean()), "keep_exact": float(rw[ki].mean()),
           "selection": 0.7 * float(rw[gi].mean()) + 0.3 * float(rw[ki].mean()),
           "sari_generated": float(np.mean([sari_sentence(rows[i]["source"], out[i], [rows[i]["target"]]) for i in gi])),
           "judge_same_mean": float(np.nanmean(info["meaning"][gi])),
           "lead_ge2": float(np.mean(np.nan_to_num(info["lead"][gi], nan=-9) >= 2)),
           "gates_pass": float(info["gate"][gi].mean()),
           "copy_hard": float(np.mean([out[i].strip() == rows[i]["source"].strip() for i in gi])),
           "seconds": time.time() - t0}
    for t in ("identity", "protected", "short"):
        ix = [i for i in ki if rows[i]["pair_type"] == t]
        if ix: res[f"keep_{t}"] = float(rw[ix].mean())
    results[name] = res
    print(name, json.dumps(res), flush=True)
    with open(Path(a.out).with_suffix(f".{name}.preds.jsonl"), "w", encoding="utf-8") as f:
        for r, p in zip(rows, out): f.write(json.dumps({"id": r["id"], "pair_type": r["pair_type"], "prediction": p}, ensure_ascii=False) + "\n")
    del model; torch.cuda.empty_cache()
json.dump(results, open(a.out, "w"), indent=1)
print("EXIT=0")
