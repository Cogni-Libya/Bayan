#!/usr/bin/env bash
# One-time setup on a fresh GPU box (run as the instance's on-start command): install vLLM and the
# pipeline's Python deps, and prefetch both model checkpoints in parallel so they are on disk by the
# time the code has been copied over. Progress: /root/bootstrap.log; done when it prints BOOTSTRAP_DONE.
set -uo pipefail
exec >> /root/bootstrap.log 2>&1
GEN_MODEL=${GEN_MODEL:-google/gemma-4-31B-it-qat-w4a16-ct}
JUDGE_MODEL=${JUDGE_MODEL:-RedHatAI/Qwen3.8-27B-INT4}

pip install -q uv
uv pip install --system -q "huggingface_hub[hf_transfer]"
export HF_HUB_ENABLE_HF_TRANSFER=1
hf download "$GEN_MODEL" > /root/dl_gen.log 2>&1 &
hf download "$JUDGE_MODEL" > /root/dl_judge.log 2>&1 &
uv pip install --system -q "vllm>=0.17" dspy polars python-dotenv tqdm onnxruntime tokenizers wordfreq
wait
echo "vllm $(python -c 'import vllm; print(vllm.__version__)')"
echo BOOTSTRAP_DONE
