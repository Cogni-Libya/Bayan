#!/usr/bin/env bash
# Serve the corpus-generation models on a 2-GPU box: generator on GPU 0 (:8000), judge on GPU 1 (:8001).
# The judge GPU keeps ~15% free for the CAMeL readability model the pipeline loads there.
#   GEN_MODEL=... JUDGE_MODEL=... bash scripts/remote/serve_vllm.sh      # logs: vllm_gen.log, vllm_judge.log
set -euo pipefail
GEN_MODEL=${GEN_MODEL:-google/gemma-4-31B-it-qat-w4a16-ct}
JUDGE_MODEL=${JUDGE_MODEL:-RedHatAI/Qwen3.8-27B-INT4}
MAX_MODEL_LEN=${MAX_MODEL_LEN:-8192}
LOG_DIR=${LOG_DIR:-.}
COMMON=(--max-model-len "$MAX_MODEL_LEN" --enable-prefix-caching --limit-mm-per-prompt '{"image":0,"video":0,"audio":0}')

CUDA_VISIBLE_DEVICES=0 nohup vllm serve "$GEN_MODEL" --port 8000 --gpu-memory-utilization 0.92 "${COMMON[@]}" \
  > "$LOG_DIR/vllm_gen.log" 2>&1 < /dev/null &
CUDA_VISIBLE_DEVICES=1 nohup vllm serve "$JUDGE_MODEL" --port 8001 --gpu-memory-utilization 0.82 "${COMMON[@]}" \
  > "$LOG_DIR/vllm_judge.log" 2>&1 < /dev/null &

for port in 8000 8001; do
  until curl -sf "localhost:$port/v1/models" > /dev/null; do sleep 10; done
  echo "READY :$port"
done
