"""Run the quantized ONNX MARBERT classifier over the ENTIRE BAREC corpus and report
error-type breakdowns (TP/TN/FP/FN for the easy/hard band decision, plus the full 4-way
confusion matrix), split by whether each sentence was in training or held out.

IMPORTANT framing: MARBERT was fine-tuned on ~63k of BAREC's ~67.6k sentences (everything
outside the fixed 800-sentence balanced held-out test set). Running over the whole corpus
necessarily includes those training sentences, which the model has already seen and fit --
numbers over that portion are NOT a fair measure of generalization, they're closer to
training-set fit. This script reports THREE separate views (held-out / train-seen /
combined-whole-corpus) rather than one blended number, specifically so training-set
memorization doesn't get mistaken for real generalization performance.

Uses the quantized ONNX model (models/level_classifier_bert_marbert_onnx_int8/, 164MB,
already validated on the held-out set: 87.2% band accuracy, 95.1% agreement with the
original fp32 model) -- batched inference, CPU only, no GPU needed.

Usage:
    uv run --with "optimum[onnxruntime]" --with torch --with polars python scripts/run_marbert_full_corpus.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import polars as pl
from optimum.onnxruntime import ORTModelForSequenceClassification
from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import EASY_LEVEL_CEILING, PROJECT_ROOT, load_and_clean_barec  # noqa: E402
from optimize_level_classifier import PER_LEVEL_TOTAL, PER_LEVEL_TRAIN, SEED, build_balanced_sample  # noqa: E402

QUANT_DIR = PROJECT_ROOT / "models" / "level_classifier_bert_marbert_onnx_int8"
BATCH_SIZE = 32
OUT_PATH = PROJECT_ROOT / "data" / "processed" / "marbert_full_corpus_predictions.parquet"


def predict_batched(model, tokenizer, texts: list[str]) -> np.ndarray:
    preds = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i : i + BATCH_SIZE]
        inputs = tokenizer(batch, return_tensors="pt", truncation=True, max_length=128, padding=True)
        outputs = model(**inputs)
        batch_preds = outputs.logits.argmax(dim=-1).numpy() + 1
        preds.append(batch_preds)
        if (i // BATCH_SIZE) % 50 == 0:
            print(f"  {i}/{len(texts)}...", flush=True)
    return np.concatenate(preds)


def confusion_counts(true_level: np.ndarray, pred_level: np.ndarray) -> dict:
    """TP/TN/FP/FN for the easy/hard band decision: positive = hard (level > EASY_LEVEL_CEILING)."""
    true_hard = true_level > EASY_LEVEL_CEILING
    pred_hard = pred_level > EASY_LEVEL_CEILING
    tp = int((true_hard & pred_hard).sum())
    tn = int((~true_hard & ~pred_hard).sum())
    fp = int((~true_hard & pred_hard).sum())  # said hard, actually easy -- false alarm
    fn = int((true_hard & ~pred_hard).sum())  # said easy, actually hard -- MISSED, costlier direction
    n = len(true_level)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / n
    return {"n": n, "TP": tp, "TN": tn, "FP": fp, "FN": fn, "accuracy": accuracy, "precision": precision, "recall": recall, "f1": f1}


def print_confusion_block(label: str, true_level: np.ndarray, pred_level: np.ndarray) -> None:
    c = confusion_counts(true_level, pred_level)
    print(f"\n=== {label} (n={c['n']}) ===")
    print(f"  TP (correctly flagged hard):  {c['TP']:6d}")
    print(f"  TN (correctly flagged easy):  {c['TN']:6d}")
    print(f"  FP (false alarm -- said hard, was easy):  {c['FP']:6d}")
    print(f"  FN (MISSED -- said easy, was hard):       {c['FN']:6d}")
    print(f"  band accuracy: {c['accuracy']:.1%}  |  precision: {c['precision']:.1%}  |  recall: {c['recall']:.1%}  |  F1: {c['f1']:.1%}")

    exact = (true_level == pred_level).mean()
    off_by_one = (np.abs(true_level - pred_level) <= 1).mean()
    print(f"  4-way exact: {exact:.1%}  |  off-by-1: {off_by_one:.1%}")

    cm = np.zeros((4, 4), dtype=int)
    for t, p in zip(true_level, pred_level):
        cm[t - 1, p - 1] += 1
    print("  confusion matrix (rows=true, cols=predicted):")
    print("         pred=1  pred=2  pred=3  pred=4")
    for i in range(4):
        print(f"  true={i+1}  " + "  ".join(f"{cm[i,j]:6d}" for j in range(4)))


def main() -> None:
    print(f"Loading quantized ONNX MARBERT from {QUANT_DIR}...")
    model = ORTModelForSequenceClassification.from_pretrained(QUANT_DIR, file_name="model_quantized.onnx")
    tokenizer = AutoTokenizer.from_pretrained(QUANT_DIR)

    print("Loading BAREC and reconstructing the held-out/train split (same seed as training)...")
    df = load_and_clean_barec()
    balanced = build_balanced_sample(df, PER_LEVEL_TOTAL, SEED)
    train_pool_df = build_balanced_sample(balanced, PER_LEVEL_TRAIN, SEED)
    held_out_ids = set(balanced.join(train_pool_df, on="ID", how="anti")["ID"].to_list())
    print(f"total corpus: {df.shape[0]} sentences | held-out test set: {len(held_out_ids)} sentences")

    df = df.with_columns(pl.col("ID").is_in(held_out_ids).alias("is_held_out"))

    texts = df["Sentence"].to_list()
    true_level = df["Readability_Level_5"].to_numpy()

    print(f"\nRunning batched inference over all {len(texts)} sentences (batch size {BATCH_SIZE})...")
    t0 = time.time()
    pred_level = predict_batched(model, tokenizer, texts)
    elapsed = time.time() - t0
    print(f"done in {elapsed:.1f}s ({elapsed/len(texts)*1000:.2f}ms/sentence)")

    is_held_out = df["is_held_out"].to_numpy()

    print_confusion_block("HELD-OUT TEST SET (fair generalization measure)", true_level[is_held_out], pred_level[is_held_out])
    print_confusion_block("TRAINING-SEEN SENTENCES (model already fit these -- expect inflated numbers)", true_level[~is_held_out], pred_level[~is_held_out])
    print_confusion_block("WHOLE CORPUS COMBINED (mixes both -- NOT a fair generalization measure)", true_level, pred_level)

    results = pl.DataFrame(
        {
            "ID": df["ID"].to_list(),
            "text": texts,
            "true_level": true_level.tolist(),
            "predicted_level": pred_level.tolist(),
            "is_held_out": is_held_out.tolist(),
        }
    )
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results.write_parquet(OUT_PATH)
    print(f"\nsaved full per-sentence predictions to {OUT_PATH}")


if __name__ == "__main__":
    main()
