"""Fine-tune a pretrained Arabic transformer with a dual-head softmax + CORAL hybrid.

Fourth experiment in the level-classifier line. Results so far, held-out 800-sentence
test set, band accuracy (easy 1-2 vs hard 3-4):
  - LLM baseline (DSPy BootstrapFewShot):                    79.7%
  - 4-way softmax BERT, 3 epochs:                            83.5%  <- best so far
  - 4-way softmax BERT, 6 epochs:                            83.9%  (within noise of above)
  - Direct binary easy/hard BERT:                            83.4%  (within noise -- negative
    result, the predicted +2-4pt gain from concentrating capacity on one boundary didn't hold)
  - Pure CORAL ordinal regression:                           80.1%  (a real, ~3.5pt regression)

CORAL's failure has a clear architectural explanation: rank-consistency is bought by
forcing all 3 "is level > k?" decisions through ONE shared linear direction (a single
scalar per sentence, shifted by per-threshold biases). BAREC's own six difficulty
dimensions (spelling, word count, morphology, syntax, vocabulary, content) suggest
different levels get harder for different linguistic reasons -- what pushes a sentence
past level 1 (vocabulary) may not be what pushes it past level 3 (syntax/content).
Squeezing that through one shared direction is a real expressiveness bottleneck.

This script does NOT repeat that mistake. It keeps the softmax head's full, proven
capacity (a real 4-way linear layer, not a 1-dimensional bottleneck) as the model's
actual output -- inference and all reported metrics use ONLY the softmax head, exactly
like the best-performing experiment so far. The CORAL head is added purely as an
AUXILIARY loss term during training: same encoder, two heads, joint loss

    loss = cross_entropy(softmax_logits, true_level) + coral_lambda * coral_bce_loss

The hypothesis: injecting an explicit "these levels are ordered" signal as a training-time
regularizer -- without constraining the primary output's capacity -- might nudge the
shared encoder toward a more order-respecting representation and improve the softmax
head itself, even though replacing the softmax head with CORAL outright hurt.

Reuses CoralHead / level_to_targets from train_coral_classifier_bert.py. Defines its own
local compute_metrics rather than reusing train_level_classifier_bert.py's -- that script's
dataset stores 0-indexed labels (level-1), this one stores raw levels (1-4, needed as-is
by level_to_targets), and reusing the other's compute_metrics against raw labels silently
double-offsets true_level by +1 (caught via a first run that scored an impossible 9.9%
exact accuracy, below the 25% random-chance floor for 4-way classification).

Usage (needs a CUDA GPU):
    python train_hybrid_classifier_bert.py [--epochs 3] [--coral-lambda 0.5] [--smoke-test]

Outputs:
  - models/hybrid_classifier_bert/                    encoder + both heads
  - data/processed/hybrid_classifier_bert_eval_results.parquet
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl
import torch
import torch.nn as nn
from torch.utils.data import Dataset
from transformers import AutoModel, AutoTokenizer, DataCollatorWithPadding, Trainer, TrainingArguments

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import EASY_LEVEL_CEILING, PROJECT_ROOT, load_and_clean_barec  # noqa: E402
from optimize_level_classifier import PER_LEVEL_TOTAL, PER_LEVEL_TRAIN, SEED, build_balanced_sample  # noqa: E402
from train_coral_classifier_bert import NUM_LEVELS, NUM_THRESHOLDS, CoralHead, level_to_targets  # noqa: E402

BASE_MODEL = "CAMeL-Lab/bert-base-arabic-camelbert-mix"
MAX_LENGTH = 128

MODEL_OUT_DIR = PROJECT_ROOT / "models" / "hybrid_classifier_bert"
RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "hybrid_classifier_bert_eval_results.parquet"


def compute_metrics(eval_pred) -> dict:
    """Local, not reused from train_level_classifier_bert.py: this script's dataset stores
    RAW levels (1-4, needed as-is by level_to_targets for the CORAL loss), NOT the 0-indexed
    (level-1) labels that script's own dataset uses -- reusing its compute_metrics here would
    silently double-offset true_level by +1. (Caught this exact bug via a nonsensical first
    run: 9.9% exact accuracy, below the 25% random-chance floor for 4-way classification.)"""
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    true_level = np.asarray(labels)  # already 1-4, raw
    predicted_level = preds + 1  # argmax is 0-indexed, softmax_head has no other offset
    exact = (true_level == predicted_level).mean()
    off_by_one = (np.abs(true_level - predicted_level) <= 1).mean()
    band = ((true_level > EASY_LEVEL_CEILING) == (predicted_level > EASY_LEVEL_CEILING)).mean()
    return {"exact_accuracy": exact, "off_by_one_accuracy": off_by_one, "band_accuracy": band}


class HybridBertModel(nn.Module):
    def __init__(self, base_model_name: str):
        super().__init__()
        self.bert = AutoModel.from_pretrained(base_model_name)
        hidden_size = self.bert.config.hidden_size
        self.dropout = nn.Dropout(0.1)
        self.softmax_head = nn.Linear(hidden_size, NUM_LEVELS)  # primary output -- full capacity
        self.coral_head = CoralHead(hidden_size, NUM_THRESHOLDS)  # auxiliary only, unused at inference

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, **kwargs):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids)
        pooled = getattr(outputs, "pooler_output", None)
        if pooled is None:
            pooled = outputs.last_hidden_state[:, 0]
        pooled = self.dropout(pooled)
        return self.softmax_head(pooled), self.coral_head(pooled)


class SentenceLevelDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.encodings = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


class HybridTrainer(Trainer):
    def __init__(self, *args, class_weights=None, pos_weight=None, coral_lambda: float = 0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights
        self.pos_weight = pos_weight
        self.coral_lambda = coral_lambda

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")  # 1..4
        softmax_logits, coral_logits = model(**inputs)

        cw = self.class_weights.to(softmax_logits.device) if self.class_weights is not None else None
        ce_loss = nn.functional.cross_entropy(softmax_logits, labels - 1, weight=cw)  # 0-indexed targets

        pw = self.pos_weight.to(coral_logits.device) if self.pos_weight is not None else None
        targets = level_to_targets(labels)
        coral_loss = nn.functional.binary_cross_entropy_with_logits(coral_logits, targets, pos_weight=pw)

        loss = ce_loss + self.coral_lambda * coral_loss
        return (loss, {"logits": softmax_logits}) if return_outputs else loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):
        inputs = self._prepare_inputs(inputs)
        labels = inputs.get("labels")
        with torch.no_grad():
            loss, outputs = self.compute_loss(model, dict(inputs), return_outputs=True)
        return (loss, outputs["logits"].detach(), labels)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--coral-lambda", type=float, default=0.5, help="weight of the auxiliary CORAL loss")
    args = parser.parse_args()

    has_cuda = torch.cuda.is_available()
    print(f"CUDA available: {has_cuda}" + ("" if has_cuda else "  -- WARNING: this will be very slow on CPU"))

    print("Loading BAREC and reconstructing the SAME held-out split as the other experiments...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)
    train_pool_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    test_df = balanced.join(train_pool_df, on="ID", how="anti")
    assert test_df.shape[0] == 800, f"expected 800 held-out sentences, got {test_df.shape[0]}"

    fine_tune_pool = df.join(balanced, on="ID", how="anti")
    fine_tune_pool = fine_tune_pool.sample(fraction=1.0, shuffle=True, seed=SEED)

    if args.smoke_test:
        fine_tune_pool = fine_tune_pool.head(500)
        args.epochs = 1
        print("--smoke-test: using 500 training sentences, 1 epoch, for a quick end-to-end sanity check only.")

    n_dev = max(1, int(fine_tune_pool.shape[0] * 0.05))
    dev_df = fine_tune_pool.head(n_dev)
    train_df = fine_tune_pool.tail(-n_dev)
    print(f"train: {train_df.shape[0]} | dev: {dev_df.shape[0]} | held-out test: {test_df.shape[0]} | coral_lambda: {args.coral_lambda}")

    print(f"\nLoading tokenizer and base model: {BASE_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = HybridBertModel(BASE_MODEL)
    for param in model.parameters():  # same safetensors-contiguity fix as the CORAL script
        param.data = param.data.contiguous().clone()

    train_labels = train_df["Readability_Level_5"].to_list()
    dev_labels = dev_df["Readability_Level_5"].to_list()
    test_labels = test_df["Readability_Level_5"].to_list()

    train_ds = SentenceLevelDataset(train_df["Sentence"].to_list(), train_labels, tokenizer)
    dev_ds = SentenceLevelDataset(dev_df["Sentence"].to_list(), dev_labels, tokenizer)
    test_ds = SentenceLevelDataset(test_df["Sentence"].to_list(), test_labels, tokenizer)

    counts = np.bincount(train_labels, minlength=5)[1:].astype(np.float32)  # levels 1..4
    class_weights = torch.tensor(counts.sum() / (NUM_LEVELS * np.maximum(counts, 1)), dtype=torch.float32)

    targets = level_to_targets(torch.tensor(train_labels))
    pos_counts = targets.sum(dim=0)
    neg_counts = targets.shape[0] - pos_counts
    pos_weight = (neg_counts / pos_counts.clamp(min=1)).float()
    print(f"training level distribution: {counts.astype(int).tolist()}  |  class_weights: {class_weights.tolist()}  |  coral pos_weight: {pos_weight.tolist()}")

    steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    warmup_steps = max(1, int(0.06 * steps_per_epoch * args.epochs))

    training_args = TrainingArguments(
        output_dir=str(PROJECT_ROOT / "models" / "_hybrid_classifier_bert_checkpoints"),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.lr,
        weight_decay=0.01,
        warmup_steps=warmup_steps,
        eval_strategy="epoch",
        save_strategy="epoch",
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="band_accuracy",
        greater_is_better=True,
        fp16=has_cuda,
        logging_steps=100,
        report_to="none",
        seed=SEED,
        label_names=["labels"],
    )

    trainer = HybridTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
        class_weights=class_weights,
        pos_weight=pos_weight,
        coral_lambda=args.coral_lambda,
    )

    print("\nTraining...")
    trainer.train()

    print(f"\nEvaluating on the {len(test_ds)}-sentence held-out TEST set (never seen during training)...")
    test_output = trainer.predict(test_ds)
    test_metrics = compute_metrics((test_output.predictions, test_output.label_ids))
    print(
        f"  [hybrid_bert] exact: {test_metrics['exact_accuracy']:.1%}  |  "
        f"off-by-1: {test_metrics['off_by_one_accuracy']:.1%}  |  "
        f"easy/hard band: {test_metrics['band_accuracy']:.1%}  (0 failures)"
    )
    print("  compare against: LLM 79.7% | 4-way (3ep) 83.5% | 4-way (6ep) 83.9% | binary 83.4% | pure CORAL 80.1%")

    preds = np.argmax(test_output.predictions, axis=-1) + 1
    results = pl.DataFrame(
        {
            "classifier": "hybrid_bert",
            "text": test_df["Sentence"].to_list(),
            "true_level": test_labels,
            "predicted_level": preds.tolist(),
            "failed": [False] * len(preds),
        }
    )
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(RESULTS_PATH)
    print(f"\nsaved per-example held-out predictions to {RESULTS_PATH}")

    MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.model.bert.save_pretrained(str(MODEL_OUT_DIR / "encoder"))
    tokenizer.save_pretrained(str(MODEL_OUT_DIR / "encoder"))
    torch.save(trainer.model.softmax_head.state_dict(), str(MODEL_OUT_DIR / "softmax_head.pt"))
    torch.save(trainer.model.coral_head.state_dict(), str(MODEL_OUT_DIR / "coral_head.pt"))
    print(f"saved encoder + both heads to {MODEL_OUT_DIR}")


if __name__ == "__main__":
    main()
