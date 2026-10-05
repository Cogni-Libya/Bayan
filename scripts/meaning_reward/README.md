# BayanSimplify-v0.3 (model 3): training, the fluency retrain, and app-style evaluation

Everything that trained and evaluated BayanSimplify-v0.3 (AraT5v2 on corpus v1) and the attempts around it. Results and
decisions are on #48. All models are graded on BayanBench v2 (#48) with Gemma 4 31B and human raters, never with the
meaning judge used inside training.

**Environment.** Generation needs transformers 4.x (4.57.6 tested). transformers 5 breaks AraT5's weight tying and
AraBART's special tokens. Training was run on one vast.ai A6000.

## BayanSimplify-v0.3 (the app's large model, our best)

AraT5v2 (`UBC-NLP/AraT5v2-base-1024`) trained on corpus v1 only, with BayanSimplify-v0.2's recipe and the prefix «بسط: » (no
shadda; BayanSimplify-v0.2 used «بسّط: »). Early-stopped at step 6,341; best checkpoint 5,222 (SARI on changed dev rows 54.7).
Weights: [`Congi-libya/BayanSimplify-v0.3`](https://huggingface.co/Congi-libya/BayanSimplify-v0.3) (public); int8 bundle: `Congi-libya/BayanSimplify-ONNX`, `v0.3/`.

```bash
python scripts/meaning_reward/prepare_v1.py --out data/processed/meaning_reward/v1
python scripts/meaning_reward/train_mix.py --run arat5-v1 --model UBC-NLP/AraT5v2-base-1024 \
    --train v1/train.jsonl --select v1/dev.jsonl --evals v1/test.jsonl --out runs --prefix "بسط: "
```

`train_mix.py` is BayanSimplify-v0.2's `train.py` with bf16, no time limit and the additions below, all off by default, so the
command above is BayanSimplify-v0.3's run.

## Fluency retrain (BayanSimplify-v0.3 + SAMER + denoising)

Gemma 31B rated BayanSimplify-v0.3's Arabic correctness well below corpus v1's own targets (0.56 vs 0.72), so the retrain adds
fluent targets and a repair task:

| script | what it does |
|---|---|
| `build_mix.py` | corpus v1 train + SAMER L5→L3 (bench-overlapping fragments dropped) + 5.7k denoising rows (v1 targets with words dropped/swapped, prefix «صحح: »); 31,976 rows. **SAMER is team-only: never publish the mix.** |
| `train_mix.py` | from BayanSimplify-v0.3, 4 epochs, lr 5e-5, embeddings trainable, `--keep-ckpts 1` |
| `select_fluency.py` | rule fixed before results: highest Gemma Arabic among checkpoints with SARI ≥ best − 1 and P(same) ≥ BayanSimplify-v0.3's; scored on 400 v1 dev rows |
| `extra_questions.py` | Gemma 31B "Arabic correct / easier / coherent" scores (also `--pairs` for any source/prediction file) |

```bash
python scripts/meaning_reward/build_mix.py --v1 v1 --samer SAMER_DIR --bench BENCH_DATA --out mix
python scripts/meaning_reward/train_mix.py --run arat5-v1-mix --model Congi-libya/BayanSimplify-v0.3 \
    --train mix/train_mix.jsonl --select mix/dev.jsonl --evals mix/test.jsonl --out runs --prefix "بسط: " \
    --epochs 4 --lr 5e-5 --patience 3 --keep-ckpts 1
python scripts/meaning_reward/select_fluency.py gen --ckpts runs/arat5-v1-mix/ckpt --ref Congi-libya/BayanSimplify-v0.3 --dev mix/dev.jsonl --out sel
python scripts/meaning_reward/extra_questions.py --pairs sel/pairs.jsonl --out sel/extra.jsonl   # runs Gemma 4 31B in vLLM (GPU ≥ 44 GB)
bayanbench meaning sel/pairs.jsonl --questions same -o sel/meaning.jsonl
python scripts/meaning_reward/select_fluency.py pick --run runs/arat5-v1-mix --out sel
```

The rule picked checkpoint 3,996: Arabic 0.585 vs 0.576 and P(same) 0.636 vs 0.628 for BayanSimplify-v0.3, SARI −1. Earlier
checkpoints were more fluent and faithful but simplified less. Weights: `Congi-libya/bayan-arat5-v1-mix` (private).

## App-style outputs and decoding

| script | what it does |
|---|---|
| `predict_net.py` | bench outputs through the app's pipeline (pieces, guards, greedy or `--num-beams`, PyTorch or ONNX), plain and with the per-sentence **safety net**: a sentence that drops a number or Latin token, or changes the count of negation/limit/condition words, is shown unchanged |
| `hybrid_conf.py` | confidence-gated decoding: greedy everywhere, beam search on the least-confident share of sentences (by mean token log-prob); writes outputs for shares 0–100% |
| `onnx_export.py` | optimum ONNX export + int8 (dynamic, per-tensor). Per-channel int8 (MatMul or MatMul+Gather) breaks BayanSimplify-v0.3's output completely; per-tensor keeps it fluent but copies more |

## Comparisons

| script | what it does |
|---|---|
| `bench_all_gen.py`, `compare_report.py` | all-systems comparison: BayanBench meaning, human ratings, SARI (corpus v1, SAMER L3), Arabic proxies, size and CPU speed |
| `eval_models.py`, `rerank_bestofn.py` | same-reward comparison on corpus v1; best-of-N reranking headroom |
| `mimo_pilot.py` | MiMo as a second judge, against Marwan's pass rule (AUC ≥ 0.79 and siding with humans where Gemma disagrees). It failed: AUC 0.80, but it sided with the humans on only 31/62 disagreements |

## Tried and dropped

- **MRT** (`train_mrt.py`, `reward.py`, `serve_judge.sh`): AraBART with the meaning judge inside the loss,
  `loss = MLE + λ·Σ_y Q(y|x)·(1 − reward)`. Outputs got simpler but not more faithful. `reward.py` gates numbers and
  corpus v1's structure rules (`corpus_constraints.py`, vendored from PR #45), then multiplies judge P(same) by the
  readability lead.
- **Student DPO** (`dpo_sample.py`, `dpo_pairs.py`, `dpo_train.py`): preference pairs from BayanSimplify-v0.3's own samples.
