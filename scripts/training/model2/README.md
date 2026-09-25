## AraBART

- **Command**: Executed via Kaggle Notebook (`scripts/training/model2/model2_arabart.ipynb`), running the team's model-2 `train.py` with `--model moussaKam/AraBART --lr 5e-5`
- **Input prefix**: `بسط: ` (no shadda, unlike model 1's `بسّط: `); inference and the app must send exactly this prefix
- **GPU**: T4 GPU
- **Training Time**: 2,599s
- **Best Step**: 12,780
- **Best SARI (sari_changed)**: 64.71 on `select_dev.jsonl`, the validation set used to pick the checkpoint; test-set scores come from the evaluation task (#30)
- **Speed**: 292.8 sentences/s on the SAMER test sources (fp16, batch 64, greedy), against 80.8 for model 1 on the same run (`speed_benchmark.ipynb`)
- **Hugging Face Repo Name**: `Congi-libya/bayan-model2-arabart` (private; the org's name is spelled Congi-libya)
