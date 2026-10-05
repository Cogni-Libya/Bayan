# Model 2

`train.py` trains both models: it picks the checkpoint on SARI over the 600 changed rows of `select_dev.jsonl`, then generates greedily on every test file. `sari.py` is the SARI implementation it scores with. The training data is the private Kaggle dataset `marwanelamami13/bayan-model2-data`.

## AraT5v2

- **Command**: Executed via Kaggle Notebook (`scripts/training/model2/model2_arat5.ipynb`), running `train.py` with its defaults (`UBC-NLP/AraT5v2-base-1024`): 10 epochs, lr 1e-4, batch 8 × 2 gradient accumulation, fp16, max length 256, seed 42
- **Input prefix**: `بسّط: ` (with shadda, as model 1); inference and the app must send exactly this prefix
- **GPU**: T4 GPU (`CUDA_VISIBLE_DEVICES=0`, so the notebook's T4 x2 does not split the batch)
- **Training Time**: 6,783s, plus 702s generating the 9 test files
- **Best Step**: 14,200 of 14,210, the last evaluation; the score was still rising at 10 epochs
- **Best SARI (sari_changed)**: 66.58 on `select_dev.jsonl`, the validation set used to pick the checkpoint; test-set scores come from the evaluation task (#30)
- **Copying**: the copy rate on `select_dev.jsonl` fell from 80% at epoch 0.5 to 51% at the end. The model still returns 186 of the 600 changed rows unchanged (31%), so copying is reduced, not solved
- **Hugging Face Repo Name**: `Congi-libya/bayan-model2-arat5` (private)

## AraBART

- **Command**: Executed via Kaggle Notebook (`scripts/training/model2/model2_arabart.ipynb`), running the team's model-2 `train.py` with `--model moussaKam/AraBART --lr 5e-5`
- **Input prefix**: `بسط: ` (no shadda, unlike model 1's `بسّط: `); inference and the app must send exactly this prefix
- **GPU**: T4 GPU
- **Training Time**: 2,599s
- **Best Step**: 12,780
- **Best SARI (sari_changed)**: 64.71 on `select_dev.jsonl`, the validation set used to pick the checkpoint; test-set scores come from the evaluation task (#30)
- **Speed**: 292.8 sentences/s on the SAMER test sources (fp16, batch 64, greedy), against 80.8 for model 1 on the same run (`speed_benchmark.ipynb`)
- **Hugging Face Repo Name**: `Congi-libya/bayan-model2-arabart` (private; the org's name is spelled Congi-libya)
