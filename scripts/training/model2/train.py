"""Train a seq2seq Arabic simplifier (AraT5v2 or AraBART), choose the checkpoint on SARI over the
SAMER-dev rows that people changed, then generate greedily on every test file.

  python train.py --run model2 --train train.jsonl --select select_dev.jsonl --evals test_*.jsonl
  python train.py --run model2-arabart --model moussaKam/AraBART --prefix "بسط: " --lr 5e-5 ...

Design choices, and why:
  - The checkpoint is chosen on the 600 changed rows of select_dev.jsonl; its 300 unchanged rows are
    only logged. On a set full of unchanged rows, a model that copies its input scores highest.
  - SARI is computed against the raw reference text, not tokenizer-decoded labels.
  - Every source starts with a strength tag ([S0] minimal, [S1]-[S3] light to strong, [SA] everyday
    style). The tag is part of the input only; it is removed before any metric and from the saved predictions.
  - group_by_length=False: in transformers 4.46 True also shuffles the evaluation set, so every
    prediction would be scored against another row's reference. compute_metrics stops the run if
    the evaluation labels are ever out of order.
  - fp16 (Kaggle T4/P100 have no bf16); a non-finite loss stops the run.
  - Generation: greedy, max length 256, no repeated 4-grams (stops rare loops on long text).
"""
import argparse, json, math, os, random, sys, time

import numpy as np
import torch
from torch.utils.data import Dataset
from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq,
                          EarlyStoppingCallback, Seq2SeqTrainer, Seq2SeqTrainingArguments,
                          T5Tokenizer, TrainerCallback, set_seed)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sari import sari_sentence

p = argparse.ArgumentParser()
p.add_argument("--run", required=True)
p.add_argument("--train", required=True)
p.add_argument("--select", required=True)
p.add_argument("--evals", nargs="+", required=True)
p.add_argument("--model", default="UBC-NLP/AraT5v2-base-1024")
p.add_argument("--prefix", default="بسّط: ")
p.add_argument("--out", default="/kaggle/working")
p.add_argument("--epochs", type=float, default=10)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--bs", type=int, default=8)
p.add_argument("--accum", type=int, default=2)
p.add_argument("--evals-per-epoch", type=int, default=2)
p.add_argument("--patience", type=int, default=3)
p.add_argument("--fp16", type=int, default=1)
p.add_argument("--max-len", type=int, default=256)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--max-hours", type=float, default=8.5)   # stop training, keep time to generate
p.add_argument("--no-repeat-ngram", type=int, default=4)
a = p.parse_args()

set_seed(a.seed); random.seed(a.seed)
run_dir = os.path.join(a.out, a.run)
os.makedirs(run_dir, exist_ok=True)
json.dump(vars(a), open(f"{run_dir}/config.json", "w"), ensure_ascii=False, indent=1)
t0 = time.time()
log = lambda *x: print(f"[{a.run} {time.time() - t0:7.0f}s]", *x, flush=True)

def load(path): return [json.loads(l) for l in open(path, encoding="utf-8")]
import re as _re
def untag(s): return _re.sub(r"^\[[A-Z0-9-]+\] ", "", s)   # style tag is input only, never part of the metric

# ---------------------------------------------------------------- model ----
if "arat5" in a.model.lower():        # the fast tokenizer fails for AraT5v2; model 1 used the slow one
    from huggingface_hub import hf_hub_download
    tok_dir = f"{run_dir}/tokenizer"; os.makedirs(tok_dir, exist_ok=True)
    import shutil
    sp = f"{a.model}/spiece.model" if os.path.isdir(a.model) else hf_hub_download(a.model, "spiece.model")
    shutil.copy(sp, f"{tok_dir}/spiece.model")
    json.dump({"model_max_length": 1024, "tokenizer_class": "T5Tokenizer", "legacy": True},
              open(f"{tok_dir}/tokenizer_config.json", "w"))
    tok = T5Tokenizer.from_pretrained(tok_dir, local_files_only=True)
else:
    tok = AutoTokenizer.from_pretrained(a.model)
model = AutoModelForSeq2SeqLM.from_pretrained(a.model)
if "arat5" in a.model.lower():
    model.config.tie_word_embeddings = False          # as model 1
log("model", a.model, f"{sum(x.numel() for x in model.parameters()) / 1e6:.0f}M params")

class Pairs(Dataset):
    def __init__(self, rows):
        src = tok([a.prefix + r["source"] for r in rows], max_length=a.max_len, truncation=True)
        tgt = tok(text_target=[r["target"] for r in rows], max_length=a.max_len, truncation=True)
        self.items = [{"input_ids": s, "attention_mask": m, "labels": l}
                      for s, m, l in zip(src["input_ids"], src["attention_mask"], tgt["input_ids"])]
    def __len__(self): return len(self.items)
    def __getitem__(self, i): return self.items[i]

train_rows, sel_rows = load(a.train), load(a.select)
train_ds, sel_ds = Pairs(train_rows), Pairs(sel_rows)
log(f"train {len(train_ds)}  select {len(sel_ds)}")
sel_changed = [untag(r["source"]) != r["target"] for r in sel_rows]
# the references as the tokenizer round-trips them: used only to prove eval order is intact
sel_expected = [x.strip() for x in tok.batch_decode([it["labels"] for it in sel_ds.items], skip_special_tokens=True)]

def compute_metrics(ev):
    preds = ev.predictions[0] if isinstance(ev.predictions, tuple) else ev.predictions
    preds = np.where(preds >= 0, preds, tok.pad_token_id)
    out = [x.strip() for x in tok.batch_decode(preds, skip_special_tokens=True)]
    labels = np.where(ev.label_ids >= 0, ev.label_ids, tok.pad_token_id)
    got = [x.strip() for x in tok.batch_decode(labels, skip_special_tokens=True)]
    aligned = sum(g == e for g, e in zip(got, sel_expected)) / len(sel_expected)
    if aligned < 0.99:
        raise RuntimeError(f"eval rows out of order: only {aligned:.1%} of labels match the selection set")
    s = [sari_sentence(untag(r["source"]), o, [r["target"]]) for r, o in zip(sel_rows, out)]
    ch = [x for x, c in zip(s, sel_changed) if c]
    un_edit = [o != untag(r["source"]) for r, o, c in zip(sel_rows, out, sel_changed) if not c]
    copy = [o == untag(r["source"]) for r, o in zip(sel_rows, out)]
    return {"sari_changed": float(np.mean(ch)), "sari_all": float(np.mean(s)),
            "edit_rate_unchanged": 100 * float(np.mean(un_edit)), "copy_rate": 100 * float(np.mean(copy)),
            "aligned": 100 * aligned}

class FiniteLoss(TrainerCallback):
    def on_log(self, args, state, control, logs=None, **kw):
        if logs and "loss" in logs and not math.isfinite(logs["loss"]):
            log("NON-FINITE LOSS, stopping"); json.dump({"nan_at_step": state.global_step},
                                                        open(f"{run_dir}/NAN", "w"))
            control.should_training_stop = True

class TimeLimit(TrainerCallback):
    def on_step_end(self, args, state, control, **kw):
        if time.time() - t0 > a.max_hours * 3600:
            if not getattr(self, "said", False): log("time limit reached, stopping"); self.said = True
            control.should_training_stop = True
            if state.global_step % max(1, args.eval_steps) != 0:
                control.should_evaluate = control.should_save = True

steps_per_epoch = math.ceil(len(train_ds) / (a.bs * a.accum))
eval_steps = max(50, steps_per_epoch // a.evals_per_epoch)
args = Seq2SeqTrainingArguments(
    output_dir=f"{run_dir}/ckpt", per_device_train_batch_size=a.bs, per_device_eval_batch_size=64,
    gradient_accumulation_steps=a.accum, learning_rate=a.lr, num_train_epochs=a.epochs,
    weight_decay=0.01, warmup_steps=100, fp16=bool(a.fp16) and torch.cuda.is_available(),
    predict_with_generate=True, generation_max_length=a.max_len, generation_num_beams=1,
    eval_strategy="steps", eval_steps=eval_steps, save_strategy="steps", save_steps=eval_steps,
    save_total_limit=1, save_only_model=True, load_best_model_at_end=True,
    metric_for_best_model="sari_changed", greater_is_better=True,
    logging_steps=50, report_to="none", seed=a.seed, group_by_length=False,   # True also shuffles the eval set (4.46)
    dataloader_num_workers=0)
trainer = Seq2SeqTrainer(model=model, args=args, train_dataset=train_ds, eval_dataset=sel_ds,
                         data_collator=DataCollatorForSeq2Seq(tok, model=model, padding=True),
                         processing_class=tok, compute_metrics=compute_metrics,
                         callbacks=[EarlyStoppingCallback(a.patience), FiniteLoss(), TimeLimit()])
log(f"{steps_per_epoch} steps/epoch, eval every {eval_steps}")
trainer.train()
t_train = time.time() - t0
json.dump(trainer.state.log_history, open(f"{run_dir}/log_history.json", "w"), indent=1)
best = {"best_checkpoint": trainer.state.best_model_checkpoint, "best_sari_changed": trainer.state.best_metric,
        "train_seconds": t_train, "steps": trainer.state.global_step}
log("best", best)
trainer.save_model(f"{run_dir}/model"); tok.save_pretrained(f"{run_dir}/model")
import shutil; shutil.rmtree(f"{run_dir}/ckpt", ignore_errors=True)

# ------------------------------------------------------------ generation ----
model = trainer.model.eval()
dev = model.device
@torch.no_grad()
def generate(sources, bs=64):
    order = sorted(range(len(sources)), key=lambda i: len(sources[i]))
    out = [None] * len(sources)
    for k in range(0, len(order), bs):
        idx = order[k:k + bs]
        enc = tok([a.prefix + sources[i] for i in idx], max_length=a.max_len, truncation=True,
                  padding=True, return_tensors="pt").to(dev)
        with torch.autocast("cuda", dtype=torch.float16, enabled=bool(a.fp16) and torch.cuda.is_available()):
            g = model.generate(**enc, max_length=a.max_len, num_beams=1, do_sample=False,
                               no_repeat_ngram_size=a.no_repeat_ngram)
        for i, t in zip(idx, tok.batch_decode(g, skip_special_tokens=True)): out[i] = t.strip()
    return out

gen_times = {}
for path in a.evals:
    name = _re.sub(r"^test_", "", os.path.basename(path)).replace(".jsonl", "")
    rows = load(path); t1 = time.time()
    preds = generate([r["source"] for r in rows])
    gen_times[name] = time.time() - t1
    with open(f"{run_dir}/pred_{name}.jsonl", "w", encoding="utf-8") as f:
        for r, pr in zip(rows, preds):
            f.write(json.dumps({"id": r["id"], "source": untag(r["source"]), "prediction": pr}, ensure_ascii=False) + "\n")
    log(f"generated {name}: {len(rows)} rows in {gen_times[name]:.0f}s")
best.update({"gen_seconds": gen_times, "total_seconds": time.time() - t0})
json.dump(best, open(f"{run_dir}/summary.json", "w"), indent=1)
log("done")
