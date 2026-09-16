"""Fine-tune a pretrained Arabic transformer with a CORAL ordinal-regression head.

Third experiment in the level-classifier line, after the 4-way softmax classifier
(83.5-83.9% band accuracy) and the direct binary easy/hard reframing (83.4% -- a
negative result, no better than the 4-way model despite an expert's prediction of
+2-4 points). Both of those treat the 4 levels as either unordered categories (softmax)
or collapse the order away entirely (binary). CORAL (COnsistent RAnk Logits; Cao,
Mirjalili & Raschka 2020) is the one untested idea that actually uses the fact that
levels are ORDERED: 1 < 2 < 3 < 4, not just four unrelated buckets.

Real precedent: the ZAI team at BAREC Shared Task 2025 used exactly this technique
("ZAI at BAREC Shared Task 2025: AraBERT CORAL for Fine Grained Arabic Readability" --
verified against the real paper, not assumed).

How CORAL works: instead of a K-way softmax, it trains K-1 binary "is the true level
greater than threshold k?" classifiers (K=4 levels -> 3 thresholds: >1, >2, >3). The
key trick that makes it "rank-consistent" (guarantees monotonic predictions -- you can
never predict ">3" true but ">1" false) is that all K-1 classifiers share the SAME
weight vector on top of the encoder and differ only in a learned per-threshold bias.
Predicted level = 1 + (number of thresholds the model predicts "greater than").

Same base model (CAMeL-Lab/bert-base-arabic-camelbert-mix) and the SAME held-out
800-sentence test set as the other two experiments -- directly comparable.

Usage (needs a CUDA GPU):
    python train_coral_classifier_bert.py [--epochs 3] [--smoke-test]

Outputs:
  - models/coral_classifier_bert/                    encoder + CORAL head weights
  - data/processed/coral_classifier_bert_eval_results.parquet
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

BASE_MODEL = "CAMeL-Lab/bert-base-arabic-camelbert-mix"
MAX_LENGTH = 128
NUM_LEVELS = 4
NUM_THRESHOLDS = NUM_LEVELS - 1  # levels > 1, > 2, > 3

MODEL_OUT_DIR = PROJECT_ROOT / "models" / "coral_classifier_bert"
RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "coral_classifier_bert_eval_results.parquet"


class CoralHead(nn.Module):
    """Shared weight vector + per-threshold bias -- the part of CORAL that guarantees
    rank-monotonic predictions (P(level > 1) >= P(level > 2) >= P(level > 3) always)."""

    def __init__(self, hidden_size: int, num_thresholds: int):
        super().__init__()
        self.dropout = nn.Dropout(0.1)
        self.shared_linear = nn.Linear(hidden_size, 1, bias=False)
        self.thresholds = nn.Parameter(torch.zeros(num_thresholds))

    def forward(self, pooled: torch.Tensor) -> torch.Tensor:
        pooled = self.dropout(pooled)
        base_logit = self.shared_linear(pooled)  # (batch, 1)
        return base_logit + self.thresholds  # broadcasts -> (batch, num_thresholds)


class CoralBertModel(nn.Module):
    def __init__(self, base_model_name: str):
        super().__init__()
        self.bert = AutoModel.from_pretrained(base_model_name)
        self.head = CoralHead(self.bert.config.hidden_size, NUM_THRESHOLDS)

    def forward(self, input_ids=None, attention_mask=None, token_type_ids=None, **kwargs):
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask, token_type_ids=token_type_ids)
        pooled = getattr(outputs, "pooler_output", None)
        if pooled is None:
            pooled = outputs.last_hidden_state[:, 0]  # CLS token fallback
        return self.head(pooled)  # (batch, NUM_THRESHOLDS) raw logits


def level_to_targets(levels: torch.Tensor) -> torch.Tensor:
    """levels: 1..4 (long tensor). Returns (batch, NUM_THRESHOLDS) float targets:
    target[:, k] = 1.0 if level > (k+1) else 0.0."""
    thresholds = torch.arange(1, NUM_LEVELS, device=levels.device).unsqueeze(0)  # [1,2,3]
    return (levels.unsqueeze(1) > thresholds).float()


def logits_to_level(logits: torch.Tensor) -> torch.Tensor:
    """Predicted level = 1 + count of thresholds the model says 'greater than'."""
    exceeded = (torch.sigmoid(logits) > 0.5).sum(dim=1)
    return 1 + exceeded


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


class CoralTrainer(Trainer):
    def __init__(self, *args, pos_weight: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.pos_weight = pos_weight

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        logits = model(**inputs)
        targets = level_to_targets(labels)
        weight = self.pos_weight.to(logits.device) if self.pos_weight is not None else None
        loss = nn.functional.binary_cross_entropy_with_logits(logits, targets, pos_weight=weight)
        return (loss, {"logits": logits}) if return_outputs else loss

    def prediction_step(self, model, inputs, prediction_loss_only, ignore_keys=None):
        inputs = self._prepare_inputs(inputs)
        labels = inputs.get("labels")
        with torch.no_grad():
            loss, outputs = self.compute_loss(model, dict(inputs), return_outputs=True)
        return (loss, outputs["logits"].detach(), labels)


def compute_metrics(eval_pred) -> dict:
    logits, labels = eval_pred
    logits_t = torch.tensor(logits)
    true_level = np.asarray(labels)
    predicted_level = logits_to_level(logits_t).numpy()

    exact = (true_level == predicted_level).mean()
    off_by_one = (np.abs(true_level - predicted_level) <= 1).mean()
    band = ((true_level > EASY_LEVEL_CEILING) == (predicted_level > EASY_LEVEL_CEILING)).mean()
    return {"exact_accuracy": exact, "off_by_one_accuracy": off_by_one, "band_accuracy": band}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    has_cuda = torch.cuda.is_available()
    print(f"CUDA available: {has_cuda}" + ("" if has_cuda else "  -- WARNING: this will be very slow on CPU"))

    print("Loading BAREC and reconstructing the SAME held-out split as the other two experiments...")
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
    print(f"train: {train_df.shape[0]} | dev: {dev_df.shape[0]} | held-out test: {test_df.shape[0]}")

    print(f"\nLoading tokenizer and base model: {BASE_MODEL}...")
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = CoralBertModel(BASE_MODEL)
    # safetensors (mandatory for checkpointing in this transformers version, no opt-out) refuses
    # to save tensors that alias another tensor's storage -- BERT's loaded weights trigger this
    # on a plain (non-PreTrainedModel) nn.Module wrapper. Forcing an actual copy breaks the alias.
    for param in model.parameters():
        param.data = param.data.contiguous().clone()

    train_labels = train_df["Readability_Level_5"].to_list()
    dev_labels = dev_df["Readability_Level_5"].to_list()
    test_labels = test_df["Readability_Level_5"].to_list()

    train_ds = SentenceLevelDataset(train_df["Sentence"].to_list(), train_labels, tokenizer)
    dev_ds = SentenceLevelDataset(dev_df["Sentence"].to_list(), dev_labels, tokenizer)
    test_ds = SentenceLevelDataset(test_df["Sentence"].to_list(), test_labels, tokenizer)

    # pos_weight per threshold: (# negatives / # positives) for that threshold's binary task,
    # same imbalance-correction idea as the class_weights used in the other two experiments.
    targets = level_to_targets(torch.tensor(train_labels))
    pos_counts = targets.sum(dim=0)
    neg_counts = targets.shape[0] - pos_counts
    pos_weight = (neg_counts / pos_counts.clamp(min=1)).float()
    print(f"training level distribution: {np.bincount(train_labels, minlength=5)[1:].tolist()}  |  per-threshold pos_weight: {pos_weight.tolist()}")

    steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    warmup_steps = max(1, int(0.06 * steps_per_epoch * args.epochs))

    training_args = TrainingArguments(
        output_dir=str(PROJECT_ROOT / "models" / "_coral_classifier_bert_checkpoints"),
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
        label_names=["labels"],  # our model.forward doesn't take labels -- tell Trainer explicitly
    )

    trainer = CoralTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
        pos_weight=pos_weight,
    )

    print("\nTraining...")
    trainer.train()

    print(f"\nEvaluating on the {len(test_ds)}-sentence held-out TEST set (never seen during training)...")
    test_output = trainer.predict(test_ds)
    test_metrics = compute_metrics((test_output.predictions, test_output.label_ids))
    print(
        f"  [coral_bert] exact: {test_metrics['exact_accuracy']:.1%}  |  "
        f"off-by-1: {test_metrics['off_by_one_accuracy']:.1%}  |  "
        f"easy/hard band: {test_metrics['band_accuracy']:.1%}  (0 failures)"
    )
    print("  compare against: LLM baseline 79.7% | 4-way BERT (3ep) 83.5% | 4-way BERT (6ep) 83.9% | binary BERT (3ep) 83.4%")

    predicted_level = logits_to_level(torch.tensor(test_output.predictions)).numpy()
    results = pl.DataFrame(
        {
            "classifier": "coral_bert",
            "text": test_df["Sentence"].to_list(),
            "true_level": test_labels,
            "predicted_level": predicted_level.tolist(),
            "failed": [False] * len(predicted_level),
        }
    )
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(RESULTS_PATH)
    print(f"\nsaved per-example held-out predictions to {RESULTS_PATH}")

    MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.model.bert.save_pretrained(str(MODEL_OUT_DIR / "encoder"))
    tokenizer.save_pretrained(str(MODEL_OUT_DIR / "encoder"))
    torch.save(trainer.model.head.state_dict(), str(MODEL_OUT_DIR / "coral_head.pt"))
    print(f"saved encoder + CORAL head to {MODEL_OUT_DIR}")


if __name__ == "__main__":
    main()
