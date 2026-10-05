"""Model 2's training script (scripts/training/model2/train.py) with vast.ai defaults and three additions.

With its defaults this script trains exactly as model 3 was trained (bf16, no time limit, best of the last 3 checkpoints):
  python train_mix.py --run arat5-v1 --train v1/train.jsonl --select v1/dev.jsonl --evals v1/test.jsonl --out runs --prefix "بسط: "
Additions, all off by default:
  - a row may carry its own "prefix" (build_mix.py's denoising rows use «صحح: »); all others use --prefix;
  - --freeze-embeddings 1 keeps the shared input embeddings fixed (protects what pretraining learned);
  - --keep-ckpts 1 keeps every checkpoint, for select_fluency.py to choose among after training.
--loss-weight-from FIELD weights each row's loss by min(1, row[FIELD]/0.85). See the model 2 script's docstring below.
"""
"""Train a seq2seq Arabic simplifier (AraT5v2 or AraBART), choose the checkpoint on SARI over the
dev rows that people changed, then generate greedily on every test file.

  python train.py --run barec-v1 --train train.jsonl --select select_dev.jsonl --evals test.jsonl
  python train.py --run model2-arabart --model moussaKam/AraBART --prefix "بسط: " --lr 5e-5 ...

Design choices, and why:
  - The checkpoint is chosen on the changed rows of select_dev.jsonl; unchanged rows are only
    logged. On a set full of unchanged rows, a model that copies its input scores highest.
  - SARI is computed against the raw reference text, not tokenizer-decoded labels.
  - Sources may carry a leading strength tag ([S0], [S1]-[S3], [SA]). The tag is input only;
    it is removed before any metric and from the saved predictions.
  - group_by_length=False: in transformers 4.46 True also shuffles the evaluation set, so every
    prediction would be scored against another row's reference. compute_metrics stops the run if
    the evaluation labels are ever out of order.
  - bf16 on capable GPUs (A100/H100 on vast.ai), fp16 otherwise. A non-finite loss stops the run.
  - --loss-weight-from equivalence_score weights each row's loss by min(1, score/0.85),
    so tier-A pairs train at full weight and tier-B pairs are down-weighted.
  - Generation: greedy, max length 256, no repeated 4-grams (stops rare loops on long text).
"""
import argparse, json, math, os, random, sys, time

import numpy as np
import torch
from torch.utils.data import Dataset
from transformers import (AutoModelForSeq2SeqLM, AutoTokenizer, DataCollatorForSeq2Seq,
                          EarlyStoppingCallback, Seq2SeqTrainer, Seq2SeqTrainingArguments,
                          T5Tokenizer, TrainerCallback, set_seed)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'training', 'model2'))
from sari import sari_sentence

p = argparse.ArgumentParser()
p.add_argument("--run", required=True)
p.add_argument("--train", required=True)
p.add_argument("--select", required=True)
p.add_argument("--evals", nargs="+", required=True)
p.add_argument("--model", default="UBC-NLP/AraT5v2-base-1024")
p.add_argument("--prefix", default="بسّط: ")
p.add_argument("--out", default="./runs")
p.add_argument("--epochs", type=float, default=10)
p.add_argument("--lr", type=float, default=1e-4)
p.add_argument("--bs", type=int, default=8)
p.add_argument("--accum", type=int, default=2)
p.add_argument("--evals-per-epoch", type=int, default=2)
p.add_argument("--patience", type=int, default=3)
p.add_argument("--fp16", type=int, default=0)
p.add_argument("--bf16", type=int, default=1)
p.add_argument("--max-len", type=int, default=256)
p.add_argument("--seed", type=int, default=42)
p.add_argument("--max-hours", type=float, default=0, help="Stop training after N hours (0 = no limit)")
p.add_argument("--no-repeat-ngram", type=int, default=4)
p.add_argument("--loss-weight-from", default=None, metavar="FIELD",
               help="Weight each row's loss by min(1, row[FIELD]/0.85). Use 'equivalence_score' to down-weight tier-B pairs.")
p.add_argument("--freeze-embeddings", type=int, default=0)
p.add_argument("--keep-ckpts", type=int, default=0, help="keep every checkpoint (for a selection step after training)")
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
if a.freeze_embeddings:
    model.get_input_embeddings().weight.requires_grad_(False)
log("model", a.model, f"{sum(x.numel() for x in model.parameters()) / 1e6:.0f}M params")

class Pairs(Dataset):
    def __init__(self, rows):
        src = tok([r.get("prefix", a.prefix) + r["source"] for r in rows], max_length=a.max_len, truncation=True)
        tgt = tok(text_target=[r["target"] for r in rows], max_length=a.max_len, truncation=True)
        self.items = [{"input_ids": s, "attention_mask": m, "labels": l}
                      for s, m, l in zip(src["input_ids"], src["attention_mask"], tgt["input_ids"])]
        if a.loss_weight_from:
            for item, r in zip(self.items, rows):
                w = min(1.0, float(r.get(a.loss_weight_from, 1.0)) / 0.85)
                item["weight"] = w
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
        if a.max_hours <= 0: return
        if time.time() - t0 > a.max_hours * 3600:
            if not getattr(self, "said", False): log("time limit reached, stopping"); self.said = True
            control.should_training_stop = True
            if state.global_step % max(1, args.eval_steps) != 0:
                control.should_evaluate = control.should_save = True

class WeightedSeq2SeqTrainer(Seq2SeqTrainer):
    """Applies per-sample loss weights when --loss-weight-from is set."""
    def compute_loss(self, model, inputs, return_outputs=False, num_items_in_batch=None):
        weights = inputs.pop("weight", None)
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        # Per-token cross-entropy, then per-sample mean, then weighted mean
        loss_fct = torch.nn.CrossEntropyLoss(ignore_index=-100, reduction="none")
        flat_logits = logits.view(-1, logits.size(-1))
        flat_labels = labels.view(-1)
        token_losses = loss_fct(flat_logits, flat_labels)
        token_losses = token_losses.view(labels.size(0), -1)
        mask = (labels != -100).float()
        per_sample = (token_losses * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
        if weights is not None:
            w = torch.tensor(weights, dtype=per_sample.dtype, device=per_sample.device)
            loss = (per_sample * w).sum() / w.sum().clamp(min=1e-8)
        else:
            loss = per_sample.mean()
        return (loss, outputs) if return_outputs else loss


def make_collator(tok, model):
    base = DataCollatorForSeq2Seq(tok, model=model, padding=True)
    if not a.loss_weight_from:
        return base
    def collate(features):
        weights = [f.pop("weight", 1.0) for f in features]
        batch = base(features)
        batch["weight"] = weights
        return batch
    return collate

steps_per_epoch = math.ceil(len(train_ds) / (a.bs * a.accum))
eval_steps = max(50, steps_per_epoch // a.evals_per_epoch)
use_bf16 = bool(a.bf16) and torch.cuda.is_available() and torch.cuda.is_bf16_supported()
use_fp16 = bool(a.fp16) and torch.cuda.is_available() and not use_bf16
log(f"precision: {'bf16' if use_bf16 else 'fp16' if use_fp16 else 'fp32'}")
args = Seq2SeqTrainingArguments(
    output_dir=f"{run_dir}/ckpt", per_device_train_batch_size=a.bs, per_device_eval_batch_size=64,
    gradient_accumulation_steps=a.accum, learning_rate=a.lr, num_train_epochs=a.epochs,
    weight_decay=0.01, warmup_steps=100, fp16=use_fp16, bf16=use_bf16,
    predict_with_generate=True, generation_max_length=a.max_len, generation_num_beams=1,
    eval_strategy="steps", eval_steps=eval_steps, save_strategy="steps", save_steps=eval_steps,
    save_total_limit=None if a.keep_ckpts else 3, save_only_model=True, load_best_model_at_end=True,
    metric_for_best_model="sari_changed", greater_is_better=True,
    logging_steps=50, report_to="none", seed=a.seed, group_by_length=False,   # True also shuffles the eval set (4.46)
    dataloader_num_workers=0)
trainer_cls = WeightedSeq2SeqTrainer if a.loss_weight_from else Seq2SeqTrainer
trainer = trainer_cls(model=model, args=args, train_dataset=train_ds, eval_dataset=sel_ds,
                      data_collator=make_collator(tok, model),
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
import shutil
if not a.keep_ckpts: shutil.rmtree(f"{run_dir}/ckpt", ignore_errors=True)

# ------------------------------------------------------------ generation ----
model = trainer.model.eval()
dev = model.device
gen_dtype = torch.bfloat16 if use_bf16 else torch.float16
gen_enabled = use_bf16 or use_fp16
@torch.no_grad()
def generate(sources, bs=64):
    order = sorted(range(len(sources)), key=lambda i: len(sources[i]))
    out = [None] * len(sources)
    for k in range(0, len(order), bs):
        idx = order[k:k + bs]
        enc = tok([a.prefix + sources[i] for i in idx], max_length=a.max_len, truncation=True,
                  padding=True, return_tensors="pt").to(dev)
        with torch.autocast("cuda", dtype=gen_dtype, enabled=gen_enabled):
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
