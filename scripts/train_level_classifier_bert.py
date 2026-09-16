"""Fine-tune a pretrained Arabic transformer as a supervised readability classifier.

Replaces the LLM-prompted ClassifyReadabilityLevel signature (calibrated via few-shot
DSPy optimization on ~1,000 BAREC sentences, currently 79.7% easy/hard band accuracy)
with a small model fine-tuned on the FULL BAREC corpus (~68k sentences after reserving
the held-out test set) -- supervised training on gold labels at that scale should beat
few-shot LLM calibration, and removes an API call per classification at inference time.

Base model: CAMeL-Lab/bert-base-arabic-camelbert-mix (pretrained on MSA + Classical
Arabic + Dialectal Arabic combined -- matches BAREC's registers, which span news MSA
through Quranic/Hadith Classical Arabic).

Reuses this repo's own load_and_clean_barec() and build_balanced_sample() (same
PER_LEVEL_TOTAL/PER_LEVEL_TRAIN/SEED as optimize_level_classifier.py) so the 800-sentence
held-out TEST set is IDENTICAL to the one every other classifier variant in this project
has been evaluated on -- the final numbers this script prints are directly comparable to
the existing 79.7% band / 53.0% exact / 93.1% off-by-1 baseline, no re-derivation needed.

This needs a CUDA GPU to run in a reasonable time -- there is none on the local dev
machine. Intended to run on a rented GPU instance (e.g. vast.ai): rsync/scp this repo
(or at minimum data/raw/barec/, scripts/barec_simplification_pipeline.py,
scripts/optimize_level_classifier.py, and this file) to the instance, then:

    pip install transformers accelerate scikit-learn polars
    python scripts/train_level_classifier_bert.py

A rented mid-tier GPU (RTX 3090/4090, A10) should finish 3 epochs over ~68k short
sentences in well under an hour. Use --smoke-test to sanity-check the whole script
end-to-end on a tiny subset (runs on CPU too, just slow) before committing GPU time.

Outputs:
  - models/level_classifier_bert/          fine-tuned model + tokenizer (HF format)
  - data/processed/level_classifier_bert_eval_results.parquet   per-example test predictions
Copy the models/level_classifier_bert/ directory back to the local project once training
finishes -- that's the artifact the reranking pipeline will load.
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
    Trainer,
    TrainingArguments,
)

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import EASY_LEVEL_CEILING, PROJECT_ROOT, load_and_clean_barec  # noqa: E402
from optimize_level_classifier import PER_LEVEL_TOTAL, PER_LEVEL_TRAIN, SEED, build_balanced_sample  # noqa: E402

DEFAULT_BASE_MODEL = "CAMeL-Lab/bert-base-arabic-camelbert-mix"
NUM_LEVELS = 4  # levels 1-4 -> label ids 0-3
MAX_LENGTH = 128  # BAREC rows are single sentences; generous headroom over typical length

# Ensemble experiment: train the SAME script against different pretrained Arabic encoders
# (different pretraining corpora / tokenizers -> plausibly decorrelated errors), so output
# paths are derived from --base-model rather than hardcoded, to avoid each run overwriting
# the last. --model-tag lets a short, filesystem-safe name be given explicitly if the
# auto-derived one (base model name, slashes -> underscores) isn't what's wanted.


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


class WeightedTrainer(Trainer):
    """Standard Trainer, but with a class-weighted loss -- BAREC's natural per-level
    frequency isn't uniform (see stratified_sample's own docstring), so an unweighted
    loss would bias the model toward whichever level is most common in the wild."""

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
    true_level = labels + 1
    pred_level = preds + 1
    exact = (true_level == pred_level).mean()
    off_by_one = (np.abs(true_level - pred_level) <= 1).mean()
    band = ((true_level <= EASY_LEVEL_CEILING) == (pred_level <= EASY_LEVEL_CEILING)).mean()
    return {"exact_accuracy": exact, "off_by_one_accuracy": off_by_one, "band_accuracy": band}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke-test", action="store_true", help="tiny subset, 1 epoch, sanity-check only")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--lr", type=float, default=2e-5)
    parser.add_argument("--base-model", type=str, default=DEFAULT_BASE_MODEL, help="HF model id to fine-tune")
    parser.add_argument("--model-tag", type=str, default=None, help="output dir/file name tag; default: derived from --base-model")
    args = parser.parse_args()

    base_model = args.base_model
    model_tag = args.model_tag or base_model.replace("/", "_")
    model_out_dir = PROJECT_ROOT / "models" / f"level_classifier_bert_{model_tag}"
    results_path = PROJECT_ROOT / "data" / "processed" / f"level_classifier_bert_{model_tag}_eval_results.parquet"

    has_cuda = torch.cuda.is_available()
    print(f"CUDA available: {has_cuda}" + ("" if has_cuda else "  -- WARNING: this will be very slow on CPU"))

    print("Loading BAREC and reconstructing the SAME held-out split used elsewhere in this project...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)
    train_pool_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    test_df = balanced.join(train_pool_df, on="ID", how="anti")  # the SAME 800-sentence held-out test set
    assert test_df.shape[0] == 800, f"expected 800 held-out sentences, got {test_df.shape[0]}"

    # Everything NOT in the 1,000-sentence balanced sample is fair game for supervised training --
    # unlike the few-shot approaches, there's no reason to hold back the other ~68k labeled sentences.
    fine_tune_pool = df.join(balanced, on="ID", how="anti")
    fine_tune_pool = fine_tune_pool.sample(fraction=1.0, shuffle=True, seed=SEED)

    if args.smoke_test:
        fine_tune_pool = fine_tune_pool.head(500)
        args.epochs = 1
        print("--smoke-test: using 500 training sentences, 1 epoch, for a quick end-to-end sanity check only.")

    n_dev = max(1, int(fine_tune_pool.shape[0] * 0.05))
    dev_df = fine_tune_pool.head(n_dev)
    train_df = fine_tune_pool.tail(-n_dev)
    print(f"train: {train_df.shape[0]} | dev (training-time monitoring): {dev_df.shape[0]} | held-out test: {test_df.shape[0]}")

    print(f"\nLoading tokenizer and base model: {base_model}...")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    model = AutoModelForSequenceClassification.from_pretrained(base_model, num_labels=NUM_LEVELS)

    train_labels = (train_df["Readability_Level_5"] - 1).to_list()
    dev_labels = (dev_df["Readability_Level_5"] - 1).to_list()
    test_labels = (test_df["Readability_Level_5"] - 1).to_list()

    train_ds = SentenceLevelDataset(train_df["Sentence"].to_list(), train_labels, tokenizer)
    dev_ds = SentenceLevelDataset(dev_df["Sentence"].to_list(), dev_labels, tokenizer)
    test_ds = SentenceLevelDataset(test_df["Sentence"].to_list(), test_labels, tokenizer)

    counts = np.bincount(train_labels, minlength=NUM_LEVELS).astype(np.float32)
    class_weights = torch.tensor(counts.sum() / (NUM_LEVELS * np.maximum(counts, 1)), dtype=torch.float32)
    print(f"training label distribution (level 1-4): {counts.astype(int).tolist()}  |  class weights: {class_weights.tolist()}")

    from transformers import DataCollatorWithPadding

    steps_per_epoch = max(1, len(train_ds) // args.batch_size)
    warmup_steps = max(1, int(0.06 * steps_per_epoch * args.epochs))  # ~6% warmup, computed directly
    # since this transformers version's TrainingArguments has no warmup_ratio, only warmup_steps.

    training_args = TrainingArguments(
        output_dir=str(PROJECT_ROOT / "models" / f"_level_classifier_bert_{model_tag}_checkpoints"),
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

    print(f"\nEvaluating on the {test_ds.__len__()}-sentence held-out TEST set (never seen during training)...")
    test_output = trainer.predict(test_ds)
    test_metrics = compute_metrics((test_output.predictions, test_output.label_ids))
    print(
        f"  [{model_tag}] exact: {test_metrics['exact_accuracy']:.1%}  |  "
        f"off-by-1: {test_metrics['off_by_one_accuracy']:.1%}  |  "
        f"easy/hard band: {test_metrics['band_accuracy']:.1%}  (0 failures -- a classifier always returns a label)"
    )
    print("  compare against the existing BootstrapFewShot baseline: exact 53.0% | off-by-1 93.1% | band 79.7% | 7/800 failed")

    preds = np.argmax(test_output.predictions, axis=-1) + 1
    results = pl.DataFrame(
        {
            "classifier": model_tag,
            "text": test_df["Sentence"].to_list(),
            "true_level": test_df["Readability_Level_5"].to_list(),
            "predicted_level": preds.tolist(),
            "failed": [False] * len(preds),
        }
    )
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(results_path)
    print(f"\nsaved per-example held-out predictions to {results_path}")

    model_out_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(model_out_dir))
    tokenizer.save_pretrained(str(model_out_dir))
    print(f"saved fine-tuned model + tokenizer to {model_out_dir}")
    print("Copy this directory back to the local project -- it's what the reranking pipeline will load.")


if __name__ == "__main__":
    main()
