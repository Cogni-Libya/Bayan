#!/usr/bin/env bash
# Serve the meaning judge for train_mrt.py: vLLM pooling runner, last-token hidden state, no activation.
# The trainer applies the 4-way head (judge_head/meaning_head.safetensors) itself.
# Shares the GPU with training: --gpu-memory-utilization 0.30 leaves the rest for AraBART.
#   bash serve_judge.sh [MODEL] [PORT]       then: curl -s localhost:${PORT}/health
set -euo pipefail
MODEL=${1:-Congi-libya/bayan-meaning-judge-e2b}
PORT=${2:-8001}
exec vllm serve "$MODEL" --port "$PORT" --runner pooling \
  --pooler-config '{"pooling_type": "LAST", "use_activation": false}' \
  --max-model-len 2048 --gpu-memory-utilization "${JUDGE_GPU_UTIL:-0.30}" --enable-prefix-caching
