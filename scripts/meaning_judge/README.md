# Meaning judge: a local meaning-preservation scorer for Arabic simplification

**Models (private, Hugging Face):**
[`Congi-libya/bayan-meaning-judge-e2b`](https://huggingface.co/Congi-libya/bayan-meaning-judge-e2b) (bf16, reference) ·
[`-w8a8`](https://huggingface.co/Congi-libya/bayan-meaning-judge-e2b-w8a8) (int8, fastest) ·
[`-w4a16`](https://huggingface.co/Congi-libya/bayan-meaning-judge-e2b-w4a16) (int4 weights, smallest)

A fine-tuned Gemma 4 E2B that scores whether an Arabic rewrite keeps the meaning of its original: one forward pass,
four scores (`same`, `added`, `missing`, `contradict`). It replaces the API LLM judge (DeepSeek / Qwen through DSPy),
which was too slow and expensive to call inside a training loop and missed about a third of added claims and a quarter
of deleted content (see the adversarial test in the corpus work).

## Where to use it

| use | how |
|---|---|
| **Training reward / penalty** for the simplifier | score each generated rewrite against its source; use `same` as a continuous reward (e.g. `reward = simplicity × same`), or as a penalty `1 − same` |
| **Benchmarking** (meaning preservation of a system's outputs) | score every (source, output) pair; report mean `same` and the share below a threshold picked on the bench |
| **Data filtering** | drop synthetic pairs with low `same`; `added` / `missing` / `contradict` say why |

```python
from judge import MeaningJudge            # scripts/meaning_judge/judge.py (also shipped in the HF repos)
j = MeaningJudge("Congi-libya/bayan-meaning-judge-e2b", backend="vllm")   # or backend="transformers"
j.score([(source, rewrite), ...])        # -> [{"same", "added", "missing", "contradict", "combined"}, ...]
```

Pick the variant for your hardware: bf16 (reference), W8A8 (fastest in vLLM on Ampere or newer), W4A16 (smallest;
use `transformers` on pre-Ampere GPUs such as T4). All three are within about 1 point of each other on the bench.

## Results

The bench (`build_bench.py`, 2,779 pairs, none of its sources in the training data): DeepSeek-written adversarial
rewrites (faithful / add / delete / negate / question, 548), scripted defects (545), the team's human meaning labels
(430 pairs), Claude's blind audit of corpus v1 (1,156) and 100 unchanged copies. **Catch** = share of meaning-changing
pairs rejected at the threshold that wrongly rejects 5% of faithful pairs. `evaluate.py` prints every slice.

| scorer | planted errors: catch | human labels: AUC / catch | real subtle errors: AUC / catch | pairs/s (A6000) |
|---|---|---|---|---|
| Gemma 4 31B, zero-shot scoring mode (teacher) | 97.6% | .979 / 90.4% | .917 / 68.5% | 5.5 |
| Jev API (TypeSafe) | 93.1% | .969 / 84.6% | .870 / 64.4% | ~2 |
| Qwen3.8 27B reasoning judge (the old pipeline judge) | 92.0% | .914 / 83.9% | .766 / 55.8% | slow |
| Gemma 4 E2B, zero-shot | 61.7% | .860 / 53.8% | .782 / 39.7% | 69 |
| mDeBERTa-xnli, zero-shot (both directions) | 63.5% | .918 / 76.9% | .819 / 45.2% | 296 |
| mDeBERTa-xnli, fine-tuned 1 epoch | 76.0% | .936 / 80.8% | .832 / 56.2% | 232 |
| **meaning judge (this), bf16** | **95.5%** | **.965 / 86.5%** | **.877 / 61.6%** | **165** |
| meaning judge, W8A8 | 94.6% | .962 / 84.6% | .870 / 61.6% | 187 |
| meaning judge, W4A16 | 94.2% | .965 / 86.5% | .874 / 60.3% | 158 |

The judge reaches about **94% of Gemma 4 31B** on average (4 of 5 measures within 95%; subtle-error catch 90%)
at ~30× its speed. Accepted as good enough for a training reward.

### Zero-shot bake-off (21 scorers)

Before fine-tuning, `gpu_run.py` / `jev_run.py` scored the bench with every candidate in *scoring mode*: four yes/no
questions (`questions.py`), P(yes) read from one forward pass (no generated text).

- Gemma 4 31B scoring mode was the best judge, ahead of Jev and of the reasoning judge the pipeline used.
- Scoring mode beat reasoning mode on the same Qwen 27B (human AUC .967 vs .914).
- Small instruction models zero-shot are weak (Gemma 4 E4B .928, E2B .860, Qwen3-8B .885, SILMA-9B .907, Fanar-9B .866,
  ALLaM-7B .660, Qwen3.5-0.8B .655 human AUC).
- Embeddings (BGE-M3, Qwen3-Embedding), a reranker (bge-reranker-v2-m3) and JevEmbed are not usable (.46–.76): a
  dropped negation or an added clause barely moves an embedding.
- Rule checks (numbers, negation words, question marks) flag 17–19% of faithful rewrites; a rule veto hurts.

## How it was trained

Training pool (`VERIFIER_DATA_DIR`): 125k (source, rewrite) pairs built by the corpus-v1 work (#44 / PR #45): 69k
DeepSeek-judged and 36k Qwen-judged candidates from the synthetic pipelines, 7.5k SAMER professional rewrites (faithful),
2.8k meaning-preserving augmentations and ~10k scripted hard negatives (negation, number, quantifier, connector,
antonym, hedge drop, clause drop, addition). Every bench source is excluded (`paths.load_split`). **This data is not
in the repository**: it contains SAMER text, which may not be redistributed.

All stages: `google/gemma-4-E2B-it`, LoRA r=16 on the language model, the benchmark prompt for the "same meaning"
question, soft BCE on the (Yes − No) logit margin, 1 epoch over a 60k subsample (all planted rows + 39.5k judged).

1. **Epoch 1: Jev labels** (`train_llm_verifier.py`). Labels = Jev `same_meaning`; planted rows 0/1.
   Bench (training-script scoring, which understates all E2B stages; see the caveat below): human AUC .954,
   planted catch 83%.
   Jev hedges near 0.5 on genuine Arabic paraphrases: it passes only 54% of SAMER human rewrites while catching
   planted negations and additions (1–2% pass). English is Jev's primary language.
2. **Epoch 2: Gemma 4 31B + Jev** (`label_teacher.py`, then `train_llm_verifier.py --teacher --blend 0.7
   --init-adapter`). Gemma 4 31B labelled the 41k judged pairs in scoring mode (10.7 pairs/s on an A6000).
   On the bench the plain average of the two teachers ranks like Gemma alone; 0.7 Gemma keeps faithful rewrites near
   the top of the label range. Planted catch 83% → 91%, question flips caught 73% → 93%.
   Failure analysis: it missed small deletions inside fluent rewrites (kept 84% of the words; caught deletions kept
   59%), missed statement → question flips (no such negatives in the pool), and falsely rejected faithful rewrites that
   split a sentence into several (Jev's bias).
3. **Epoch 3: four heads + targeted data** (`build_targeted_data.py`, `label_teacher_mq.py`, `train_mh.py`).
   - 12k new rows with certain labels: 2–5-word phrase drops and adjective drops (`missing`), statement → question
     flips (`contradict`), sentence-split positives, and 2.5k real restructured rewrites that Gemma passes at ≥ 0.97.
   - Gemma 4 31B answered the added / missing / contradict questions for 20k judged pairs (plus validation); labels =
     0.85 Gemma + 0.15 Jev per question. Capped at 20k because both earlier epochs plateaued by ~25k rows.
   - A 4-output linear head on the last-token hidden state, initialised from the LM's Yes − No direction
     (`same`) and its negative (the other three).
   - Versus epoch 2, on the same training-script scoring: missed changes 120 → 86, missed question flips 19 → 0,
     missed small deletions 46 → 28, false alarms 99 → 76.
   - The `same` head alone scores as well as the combined `min(...)`; use `same`, read the others as reasons.

Then `export_judge.py` merges the LoRA into a plain text-only `Gemma4ForCausalLM` (checks it reproduces the
training-time scores) and writes the head to `judge_head/`; `quantize_judge.py` makes the W8A8 and W4A16 variants with
llm-compressor (GPTQ; `pipeline="basic"` because Gemma 4 E-models share KV across layers; no SmoothQuant, which has no
Gemma 4 mapping). `judge.py` scores with transformers or vLLM (pooling runner, last token).

> **Padding caveat (transformers 5.17).** In a padded batch (left or right padding with an attention mask) Gemma 4
> returns corrupted hidden states for some rows: identical scores for different pairs of the same length. It hit 38
> of the 2,779 bench pairs. `judge.py` batches only equal-length prompts; vLLM is unaffected. The training scripts
> still use left-padded batches, so a small share of training rows were corrupted too, and their built-in bench
> scoring understates the model. All numbers above use correct (vLLM / unpadded) scoring. A retrain without padding
> may score slightly higher.

## Reproduce

```bash
export MEANING_BENCH_DIR=data/processed/meaning_bench   # bench.jsonl, teacher labels, results
export VERIFIER_DATA_DIR=$MEANING_BENCH_DIR/verifier_data  # train.jsonl, val.jsonl, jev_labels.jsonl

python build_bench.py <main checkout> <corpus-v1 worktree> $MEANING_BENCH_DIR/bench.jsonl
# zero-shot scorers (GPU): one output file per scorer in $MEANING_BENCH_DIR
VLLM_ENABLE_V1_MULTIPROCESSING=0 python gpu_run.py llm google/gemma-4-31B-it-qat-w4a16-ct llm_gemma-4-31B.jsonl
JEV_API_KEY=... python jev_run.py $MEANING_BENCH_DIR/bench.jsonl $MEANING_BENCH_DIR/jev.jsonl

# epoch 1 and 2
python train_llm_verifier.py --model google/gemma-4-E2B-it --out runs/e2b --n-train 60000
VLLM_ENABLE_V1_MULTIPROCESSING=0 python label_teacher.py google/gemma-4-31B-it-qat-w4a16-ct $MEANING_BENCH_DIR/teacher_gemma31b.jsonl
python train_llm_verifier.py --model google/gemma-4-E2B-it --out runs/e2b_ep2 --teacher $MEANING_BENCH_DIR/teacher_gemma31b.jsonl \
  --blend 0.7 --init-adapter runs/e2b/adapter --lr 5e-5 --seed 14
# epoch 3 (the published judge); label_teacher_mq was stopped after 20,000 train rows, then run with ONLY_VAL=1
python build_targeted_data.py
VLLM_ENABLE_V1_MULTIPROCESSING=0 python label_teacher_mq.py google/gemma-4-31B-it-qat-w4a16-ct $MEANING_BENCH_DIR/teacher_gemma31b_mq.jsonl
python train_mh.py --model google/gemma-4-E2B-it --init-adapter runs/e2b_ep2/adapter --out runs/e2b_mh

python export_judge.py runs/e2b_mh export/bayan-meaning-judge-e2b
python quantize_judge.py export/bayan-meaning-judge-e2b w8a8  export/bayan-meaning-judge-e2b-w8a8     # llm-compressor venv
python quantize_judge.py export/bayan-meaning-judge-e2b w4a16 export/bayan-meaning-judge-e2b-w4a16
python judge.py export/bayan-meaning-judge-e2b $MEANING_BENCH_DIR/bench.jsonl $MEANING_BENCH_DIR/llm_ft_judge_bf16_vllm.jsonl --backend vllm
python evaluate.py                        # every scorer, every slice
```

Also here: `train_verifier.py` (the mDeBERTa cross-encoder trainer from the corpus-v1 work) and `score_ce.py`.

Compute: one RTX A6000 (vast.ai). Labelling, three training runs, export and quantization took about 10 GPU-hours
(~$6 including model downloads); the Jev relabel of the pool cost about $3.7 on TypeSafe.

## Limitations

- Catches ~62% of *subtle* real meaning changes at 5% false rejects (Gemma 4 31B: 68.5%); remaining misses are
  negations inside long sentences and subtle reference / generalisation errors the teachers also miss.
- Scores are not calibrated probabilities; choose thresholds on your own data or use the score continuously.
- Human labels: one annotator, 52 "changed" pairs (one pair ≈ 2 points of catch). The "real subtle" slice is labelled
  by Claude.
- Teacher biases carry over. Gemma 4 31B generated part of the pool but showed no self-preference (passes 87% of its
  own and of other generators' pairs); Jev is English-first.
