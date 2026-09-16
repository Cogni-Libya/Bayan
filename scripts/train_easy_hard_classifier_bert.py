"""Fine-tune a pretrained Arabic transformer as a DIRECT binary easy/hard classifier.

Companion experiment to train_level_classifier_bert.py: that script trains a 4-way
level classifier and derives "band accuracy" (levels 1-2 vs 3-4) as a post-hoc metric.
This script instead trains directly on the 2-way easy/hard split from the start, putting
all model capacity and gradient signal on the one boundary the pipeline actually gates
on, rather than also having to learn the (band-irrelevant) 1-vs-2 and 3-vs-4 distinctions.

Motivated by an expert consultation on why 83.5% band accuracy (from the 4-way model)
fell well short of a 95% target: BAREC's own inter-annotator agreement is 81.8% QWK on
the full 19-level scale (exact-match agreement only 61.4%), which puts a real, human
noise-floor-driven ceiling on ANY classifier trained on these labels -- a realistic
target is more like 88-92% band accuracy, not 95%. This binary reframing is the
highest-ranked, cheapest experiment for closing part of the remaining gap.

Same base model (CAMeL-Lab/bert-base-arabic-camelbert-mix) and the SAME held-out
800-sentence test set as train_level_classifier_bert.py (built via the same
build_balanced_sample() call, same seed) -- directly comparable. That test set is
200 sentences/level x 4 levels, so it's already an exactly balanced 400 easy / 400 hard
split for this binary framing, no rebalancing needed.

Usage (same environment as train_level_classifier_bert.py -- needs a CUDA GPU):
    python train_easy_hard_classifier_bert.py [--epochs 3] [--smoke-test]

3 epochs by default, not 6: the earlier 4-way experiment showed 6 epochs doesn't help
(dev band accuracy peaked at epoch 2 and declined after, from overfitting/miscalibration
-- loss climbing while raw accuracy still crept up). No reason to expect this binary
version behaves differently, so default to what actually worked.

Outputs:
  - models/easy_hard_classifier_bert/                fine-tuned model + tokenizer (HF format)
  - data/processed/easy_hard_classifier_bert_eval_results.parquet   per-example test predictions
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import polars as pl
import torch
from torch.utils.data import Dataset
from transformers import (
    AutoModelForSequenceClassification,
    AutoTokenizer,
    DataCollatorWithPadding,
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import EASY_LEVEL_CEILING, PROJECT_ROOT, load_and_clean_barec  # noqa: E402
from optimize_level_classifier import PER_LEVEL_TOTAL, PER_LEVEL_TRAIN, SEED, build_balanced_sample  # noqa: E402

BASE_MODEL = "CAMeL-Lab/bert-base-arabic-camelbert-mix"
MAX_LENGTH = 128

MODEL_OUT_DIR = PROJECT_ROOT / "models" / "easy_hard_classifier_bert"
RESULTS_PATH = PROJECT_ROOT / "data" / "processed" / "easy_hard_classifier_bert_eval_results.parquet"


def to_hard_label(level_col: pl.Series) -> list[int]:
    return (level_col > EASY_LEVEL_CEILING).cast(pl.Int64).to_list()  # 0 = easy, 1 = hard


class SentencePairDataset(Dataset):
    def __init__(self, texts: list[str], labels: list[int], tokenizer):
        self.encodings = tokenizer(texts, truncation=True, max_length=MAX_LENGTH, padding=False)
        self.labels = labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> dict:
        item = {k: torch.tensor(v[idx]) for k, v in self.encodings.items()}
        item["labels"] = torch.tensor(self.labels[idx])
        return item


class WeightedTrainer(Trainer):
    def __init__(self, *args, class_weights: torch.Tensor | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.class_weights = class_weights

    def compute_loss(self, model, inputs, return_outputs=False, **kwargs):
        labels = inputs.pop("labels")
        outputs = model(**inputs)
        logits = outputs.logits
        weight = self.class_weights.to(logits.device) if self.class_weights is not None else None
        loss = torch.nn.functional.cross_entropy(logits, labels, weight=weight)
        return (loss, outputs) if return_outputs else loss


def compute_metrics(eval_pred) -> dict:
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    accuracy = (preds == labels).mean()
    # precision/recall for the "hard" class specifically: a false negative here (a hard
    # sentence predicted easy) means a dyslexic reader gets no simplification when they
    # needed one -- the costlier error direction for this product, worth tracking apart
    # from plain accuracy.
    tp = int(((preds == 1) & (labels == 1)).sum())
    fp = int(((preds == 1) & (labels == 0)).sum())
    fn = int(((preds == 0) & (labels == 1)).sum())
    hard_precision = tp / (tp + fp) if (tp + fp) else 0.0
    hard_recall = tp / (tp + fn) if (tp + fn) else 0.0
    return {"band_accuracy": accuracy, "hard_precision": hard_precision, "hard_recall": hard_recall}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    args = parser.parse_args()

    has_cuda = torch.cuda.is_available()
    print(f"CUDA available: {has_cuda}" + ("" if has_cuda else "  -- WARNING: this will be very slow on CPU"))

    print("Loading BAREC and reconstructing the SAME held-out split as train_level_classifier_bert.py...")
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
    model = AutoModelForSequenceClassification.from_pretrained(BASE_MODEL, num_labels=2)

    train_labels = to_hard_label(train_df["Readability_Level_5"])
    dev_labels = to_hard_label(dev_df["Readability_Level_5"])
    test_labels = to_hard_label(test_df["Readability_Level_5"])

    train_ds = SentencePairDataset(train_df["Sentence"].to_list(), train_labels, tokenizer)
    dev_ds = SentencePairDataset(dev_df["Sentence"].to_list(), dev_labels, tokenizer)
    test_ds = SentencePairDataset(test_df["Sentence"].to_list(), test_labels, tokenizer)

    counts = np.bincount(train_labels, minlength=2).astype(np.float32)
    class_weights = torch.tensor(counts.sum() / (2 * np.maximum(counts, 1)), dtype=torch.float32)
    print(f"training label distribution (easy/hard): {counts.astype(int).tolist()}  |  class weights: {class_weights.tolist()}")

    steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    warmup_steps = max(1, int(0.06 * steps_per_epoch * args.epochs))

    training_args = TrainingArguments(
        output_dir=str(PROJECT_ROOT / "models" / "_easy_hard_classifier_bert_checkpoints"),
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
    )

    trainer = WeightedTrainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=dev_ds,
        data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
        compute_metrics=compute_metrics,
        class_weights=class_weights,
    )

    print("\nTraining...")
    trainer.train()

    print(f"\nEvaluating on the {len(test_ds)}-sentence held-out TEST set (never seen during training)...")
    test_output = trainer.predict(test_ds)
    test_metrics = compute_metrics((test_output.predictions, test_output.label_ids))
    print(
        f"  [easy_hard_bert] band accuracy: {test_metrics['band_accuracy']:.1%}  |  "
        f"hard-class precision: {test_metrics['hard_precision']:.1%}  |  "
        f"hard-class recall: {test_metrics['hard_recall']:.1%}  (0 failures)"
    )
    print("  compare against: LLM baseline 79.7% | 4-way BERT (3ep) 83.5% | 4-way BERT (6ep) 83.9%")

    preds = np.argmax(test_output.predictions, axis=-1)
    results = pl.DataFrame(
        {
            "classifier": "easy_hard_bert",
            "text": test_df["Sentence"].to_list(),
            "true_hard": test_labels,
            "predicted_hard": preds.tolist(),
            "failed": [False] * len(preds),
        }
    )
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(RESULTS_PATH)
    print(f"\nsaved per-example held-out predictions to {RESULTS_PATH}")

    MODEL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(MODEL_OUT_DIR))
    tokenizer.save_pretrained(str(MODEL_OUT_DIR))
    print(f"saved fine-tuned model + tokenizer to {MODEL_OUT_DIR}")


if __name__ == "__main__":
    main()
