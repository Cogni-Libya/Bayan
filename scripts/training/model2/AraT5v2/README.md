# Model 2: AraT5v2 Training Run

## Configuration & Environment
- **Command:** Executed via Kaggle Notebook (`scripts/training/model2/arat5/model2_arat5.ipynb`), running the team's model-2 `train.py` with default recipe:
  - 10 epochs
  - lr 1e-4
  - batch 8 × 2 gradient accumulation
  - fp16
  - max length 256
  - seed 42
- **GPU:** T4 GPU (`CUDA_VISIBLE_DEVICES=0` pinned to avoid batch-splitting across the notebook's T4 x2)
- **HF Repo:** `Congi-libya/bayan-model2-arat5` (private)

## Training Results
- **Training Time:** ~7,485s total (6,782.6s training + ~702s generation across all 9 test files)
- **Best Step:** 14,200 (out of 14,210 total steps; full 10 epochs, no early stopping)
- **Best sari_changed:** 66.58 on `select_dev.json`'s 600 changed rows (used to pick checkpoint; test-set scores from evaluation task #30)

## Observations & Notes
- **eval_copy_rate:** Dropped steadily from ~80% at epoch 0.5 to ~51% by the end of training, confirming that training on all unchanged SAMER pairs resolved the copying issue.
