"""
train_model.py
===============
Trains an AraT5v2-base-1024 model for Arabic text simplification.

Reads all hyperparameters, model name, and data/output paths from a
config.yaml file — nothing is hardcoded here — so this exact script
can later be reused for the other planned models (different data,
possibly a different model_name) just by pointing it at a different
config file.

Usage (command line):
    python train_model.py --config config.yaml

Usage on Google Colab (as a Python cell):
    import sys
    sys.argv = ["train_model.py", "--config",
                "/content/drive/MyDrive/samer_project/config.yaml"]  # EDIT ME: your Drive path
    exec(open("/content/drive/MyDrive/samer_project/train_model.py").read())

Outputs:
    - Best model checkpoint saved to config['output_dir']
    - results/samer_model_dev.md          — SARI, BLEU, copy rate (full dev)
    - results/samer_model_dev_predictions.csv — ID, original_text, reference,
      prediction for every dev row (needed to read outputs by hand for
      meaning errors, and to compare models later)

Notes on evaluation strategy:
    - Trains and evaluates on train/dev only. The test split is
      Abdul Majid's responsibility (final evaluation) — never loaded here.
    - Early stopping selects on eval_sari, NOT eval_loss. Dev loss keeps
      improving while a model learns to copy its input (SAMER's dev is
      ~43% identity pairs, so copying looks good on loss). This is a
      documented failure mode: fine-tuned T5 models can "learn to
      minimize loss by making very few changes"
      (Heineman et al., EMNLP 2023: https://aclanthology.org/2023.emnlp-main.211/).
      SARI penalizes copy-only behavior directly via its Delete/Add
      components, so it stays reliable regardless of dev's identity ratio.
    - Dev loss is still computed and logged every eval (for visibility),
      it is just not used to pick the checkpoint.
    - Generating on all ~2,983 dev rows every epoch is slow. A fixed
      random subset (~500 rows, same seed) is used for the per-epoch
      early-stopping SARI check. The FULL dev set is scored once at the
      end, after the best checkpoint is loaded, for the numbers that get
      reported.
"""

import argparse
import os

import numpy as np
import pandas as pd
import torch
import yaml
import evaluate
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    T5Tokenizer,
    AutoModelForSeq2SeqLM,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    EarlyStoppingCallback,
    set_seed,
)


class SimplificationDataset(Dataset):
    """Wraps a DataFrame with input_column/target_column into tokenized tensors."""

    def __init__(self, df: pd.DataFrame, tokenizer, config: dict):
        self.texts = df[config["input_column"]].astype(str).tolist()
        self.targets = df[config["target_column"]].astype(str).tolist()
        self.ids = df["ID"].tolist() if "ID" in df.columns else list(range(len(df)))
        self.tokenizer = tokenizer
        self.prefix = config["prefix"]
        self.max_input_length = config["max_input_length"]
        self.max_target_length = config["max_target_length"]

    def __len__(self):
        return len(self.texts)

    def __getitem__(self, idx):
        input_text = self.prefix + self.texts[idx]
        target_text = self.targets[idx]

        model_inputs = self.tokenizer(
            input_text,
            max_length=self.max_input_length,
            truncation=True,
            padding="max_length",
        )
        labels = self.tokenizer(
            target_text,
            max_length=self.max_target_length,
            truncation=True,
            padding="max_length",
        )["input_ids"]

        # Replace pad tokens with -100 so they're ignored in the loss
        labels = [
            (l if l != self.tokenizer.pad_token_id else -100) for l in labels
        ]

        return {
            "input_ids": model_inputs["input_ids"],
            "attention_mask": model_inputs["attention_mask"],
            "labels": labels,
        }


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_copy_rate(sources: list, predictions: list) -> float:
    """Share of predictions that are identical (after strip) to their input."""
    identical = sum(
        1 for src, pred in zip(sources, predictions) if src.strip() == pred.strip()
    )
    return identical / len(predictions) if predictions else 0.0


def decode_predictions_and_labels(tokenizer, predictions, labels):
    """Shared decode logic used both during training-time eval and final full-dev eval."""
    if isinstance(predictions, tuple):
        predictions = predictions[0]

    decoded_preds = tokenizer.batch_decode(predictions, skip_special_tokens=True)

    # Replace -100 back to pad_token_id before decoding labels
    labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
    decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)

    decoded_preds = [p.strip() for p in decoded_preds]
    decoded_labels = [l.strip() for l in decoded_labels]
    return decoded_preds, decoded_labels


def build_compute_metrics(tokenizer, sources: list, sari_metric, bleu_metric):
    """
    Returns a compute_metrics function closure bound to a specific list of
    source texts (either the early-stopping subset or the full dev set).
    SARI needs the original input alongside predictions and references.
    """

    def compute_metrics(eval_preds):
        predictions, labels = eval_preds
        decoded_preds, decoded_labels = decode_predictions_and_labels(
            tokenizer, predictions, labels
        )

        sari_result = sari_metric.compute(
            sources=sources,
            predictions=decoded_preds,
            references=[[l] for l in decoded_labels],
        )
        bleu_result = bleu_metric.compute(
            predictions=decoded_preds,
            references=[[l] for l in decoded_labels],
        )
        copy_rate = compute_copy_rate(sources, decoded_preds)

        return {
            "sari": sari_result["sari"],
            "bleu": bleu_result["bleu"],
            "copy_rate": copy_rate,
        }

    return compute_metrics


def main():
    parser = argparse.ArgumentParser(description="Train a seq2seq model for Arabic simplification.")
    parser.add_argument("--config", required=True,  # EDIT ME: no default on purpose — always pass an explicit config file
                         help="Path to config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    set_seed(config["seed"])

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")
    print(f"Config loaded from: {args.config}")

    # -------------------------------------------------------------
    # Load data (train + dev only — never test, per task scope)
    # -------------------------------------------------------------
    train_path = os.path.join(config["data_dir"], config["train_file"])
    dev_path = os.path.join(config["data_dir"], config["dev_file"])

    print(f"Loading train: {train_path}")
    train_df = pd.read_parquet(train_path)
    print(f"Loading dev:   {dev_path}")
    dev_df = pd.read_parquet(dev_path)

    print(f"Train rows: {len(train_df)} | Dev rows: {len(dev_df)}")

    # -------------------------------------------------------------
    # Load model and tokenizer (both name and paths come from config only)
    # -------------------------------------------------------------
    print(f"Loading model: {config['model_name']}")
    # Load the tokenizer directly as T5Tokenizer (slow, pure-Python,
    # sentencepiece-based) with legacy=True. AutoTokenizer's fast-tokenizer
    # path fails on this model's spiece.model with newer `tokenizers`
    # versions (TypeError building the Unigram model); this path avoids
    # that broken code entirely.
    try:
        tokenizer = T5Tokenizer.from_pretrained(config["model_name"], legacy=True)
    except Exception as e:
        print(f"T5Tokenizer failed ({e}), falling back to AutoTokenizer(use_fast=False)...")
        tokenizer = AutoTokenizer.from_pretrained(config["model_name"], use_fast=False)
    model = AutoModelForSeq2SeqLM.from_pretrained(config["model_name"])
    model.to(device)

    # -------------------------------------------------------------
    # Build datasets
    # -------------------------------------------------------------
    train_dataset = SimplificationDataset(train_df, tokenizer, config)

    # Fixed random subset of dev used ONLY for the per-epoch early-stopping
    # check (fast). The full dev set is scored once at the very end.
    subset_size = min(config["early_stopping_eval_subset_size"], len(dev_df))
    dev_subset_df = dev_df.sample(n=subset_size, random_state=config["seed"]).reset_index(drop=True)
    print(f"Early-stopping eval subset: {len(dev_subset_df)} rows (of {len(dev_df)} total dev rows)")

    dev_subset_dataset = SimplificationDataset(dev_subset_df, tokenizer, config)
    dev_subset_sources = dev_subset_df[config["input_column"]].astype(str).tolist()

    # -------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------
    sari_metric = evaluate.load("sari")
    bleu_metric = evaluate.load("bleu")

    # compute_metrics used DURING training is bound to the small subset
    compute_metrics_subset = build_compute_metrics(
        tokenizer, dev_subset_sources, sari_metric, bleu_metric
    )

    # -------------------------------------------------------------
    # Training arguments (all values come from config, nothing hardcoded)
    # -------------------------------------------------------------
    training_args_kwargs = dict(
        output_dir=config["output_dir"],
        logging_dir=config["logging_dir"],
        learning_rate=config["learning_rate"],
        per_device_train_batch_size=config["per_device_train_batch_size"],
        per_device_eval_batch_size=config["per_device_eval_batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        num_train_epochs=config["num_train_epochs"],
        weight_decay=config["weight_decay"],
        warmup_ratio=config["warmup_ratio"],
        # Modern transformers (we're back on latest, not the pinned 4.35.2)
        # uses the short name "eval_strategy".
        eval_strategy=config["eval_strategy"],
        save_strategy=config["save_strategy"],
        # Select the best checkpoint on SARI (computed on the fast subset
        # during training), NOT on loss. Loss is still logged every eval
        # for visibility, just not used for selection.
        metric_for_best_model=config["metric_for_best_model"],  # "eval_sari"
        greater_is_better=config["greater_is_better"],
        load_best_model_at_end=config["load_best_model_at_end"],
        predict_with_generate=True,
        generation_max_length=config["generation_max_length"],
        generation_num_beams=config["generation_num_beams"],
        seed=config["seed"],
        report_to="none",
        logging_steps=50,
        save_total_limit=config.get("save_total_limit", 2),
    )
    # Optional: if config sets eval_strategy/save_strategy to "steps"
    # (recommended on Colab/Kaggle to survive session drops mid-epoch),
    # also pass the matching step counts.
    if config.get("save_steps") is not None:
        training_args_kwargs["save_steps"] = config["save_steps"]
    if config.get("eval_steps") is not None:
        training_args_kwargs["eval_steps"] = config["eval_steps"]

    training_args = Seq2SeqTrainingArguments(**training_args_kwargs)

    early_stopping = EarlyStoppingCallback(
        early_stopping_patience=config["early_stopping_patience"]
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=dev_subset_dataset,          # fast subset during training
        compute_metrics=compute_metrics_subset,
        callbacks=[early_stopping],
    )

    # -------------------------------------------------------------
    # Train
    # -------------------------------------------------------------
    print("\nStarting training...")
    print(f"(Early stopping watches eval_sari on a {len(dev_subset_df)}-row dev "
          f"subset; eval_loss is logged too but not used for selection.)\n")
    trainer.train()

    # -------------------------------------------------------------
    # Final evaluation on the FULL dev set (best checkpoint is already
    # loaded via load_best_model_at_end). This is what gets reported.
    # -------------------------------------------------------------
    print("\nRunning final evaluation on the FULL dev set...\n")

    full_dev_dataset = SimplificationDataset(dev_df, tokenizer, config)
    full_dev_sources = dev_df[config["input_column"]].astype(str).tolist()
    full_dev_targets = dev_df[config["target_column"]].astype(str).tolist()
    full_dev_ids = dev_df["ID"].tolist() if "ID" in dev_df.columns else list(range(len(dev_df)))

    compute_metrics_full = build_compute_metrics(
        tokenizer, full_dev_sources, sari_metric, bleu_metric
    )
    trainer.compute_metrics = compute_metrics_full

    final_metrics = trainer.evaluate(eval_dataset=full_dev_dataset)
    print(final_metrics)

    # -------------------------------------------------------------
    # Generate predictions on the full dev set once, and save them —
    # needed both for manual error reading and for comparing models later.
    # -------------------------------------------------------------
    print("\nGenerating predictions on the full dev set for saving...\n")
    predict_output = trainer.predict(full_dev_dataset)
    decoded_preds, decoded_labels = decode_predictions_and_labels(
        tokenizer, predict_output.predictions, predict_output.label_ids
    )

    predictions_df = pd.DataFrame({
        "ID": full_dev_ids,
        "original_text": full_dev_sources,
        "reference": full_dev_targets,
        "prediction": decoded_preds,
    })

    # -------------------------------------------------------------
    # Save best model + tokenizer
    # -------------------------------------------------------------
    os.makedirs(config["output_dir"], exist_ok=True)
    trainer.save_model(config["output_dir"])
    tokenizer.save_pretrained(config["output_dir"])
    print(f"\nBest model saved to: {config['output_dir']}")

    # -------------------------------------------------------------
    # Write results file (results/samer_model_dev.md)
    # -------------------------------------------------------------
    os.makedirs(os.path.dirname(config["results_file"]), exist_ok=True)
    with open(config["results_file"], "w", encoding="utf-8") as f:
        f.write("# SAMER Model — Dev Results\n\n")
        f.write(f"Model: `{config['model_name']}`\n\n")
        f.write(f"Seed: `{config['seed']}`\n\n")
        f.write("## Dev metrics (best checkpoint, selected by eval_sari "
                f"on a {len(dev_subset_df)}-row subset; scored here on the "
                "full dev set)\n\n")
        f.write(f"- SARI: {final_metrics.get('eval_sari'):.4f}\n")
        f.write(f"- BLEU: {final_metrics.get('eval_bleu'):.4f}\n")
        f.write(f"- Copy rate: {final_metrics.get('eval_copy_rate'):.4f}\n")
        f.write(f"- Eval loss: {final_metrics.get('eval_loss'):.4f}  "
                "(logged for visibility only — not used to select the checkpoint)\n\n")
        f.write("Note: dev is SAMER's own split (not identity-capped), "
                "~43% identity pairs. This is expected: dev/test keep every "
                "row, including sentences that need no change, since a real "
                "user will paste sentences that are already easy and the "
                "model has to leave those alone.\n")

    print(f"Results written to: {config['results_file']}")

    # -------------------------------------------------------------
    # Save full dev predictions (ID, original_text, reference, prediction)
    # -------------------------------------------------------------
    os.makedirs(os.path.dirname(config["predictions_file"]), exist_ok=True)
    predictions_df.to_csv(config["predictions_file"], index=False, encoding="utf-8-sig")
    print(f"Dev predictions written to: {config['predictions_file']} "
          f"({len(predictions_df)} rows)")


if __name__ == "__main__":
    main()
