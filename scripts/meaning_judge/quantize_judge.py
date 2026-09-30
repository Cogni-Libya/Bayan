"""Quantize the exported meaning judge with llm-compressor (compressed-tensors format, loads in vLLM and transformers).

  python quantize_judge.py export/bayan-meaning-judge-e2b w8a8   export/bayan-meaning-judge-e2b-w8a8
  python quantize_judge.py export/bayan-meaning-judge-e2b w4a16  export/bayan-meaning-judge-e2b-w4a16

W8A8 = GPTQ int8 weights + dynamic per-token int8 activations; W4A16 = GPTQ int4 weights (group 128).
Calibration: 256 real judge prompts (judge prompt template over training pairs). Kept in full precision: lm_head and
Gemma 4's per-layer-embedding projections. The 4-way head (judge_head/) is copied unchanged (fp32, 6k parameters).
"""
import json, random, shutil, sys
from pathlib import Path

from datasets import Dataset
from llmcompressor import oneshot
from llmcompressor.modifiers.quantization import GPTQModifier
from transformers import AutoModelForCausalLM, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
from paths import BENCH, BENCH_DIR, VERIFIER_DATA

SRC, SCHEME, OUT = Path(sys.argv[1]), sys.argv[2], Path(sys.argv[3])
DATA = Path(sys.argv[4]) if len(sys.argv) > 4 else VERIFIER_DATA / "train.jsonl"
cfg = json.load(open(SRC / "judge_config.json", encoding="utf-8"))
tok = AutoTokenizer.from_pretrained(SRC)

def prompt(o, r):
    user = cfg["user_template"].format(original=o, rewrite=r, question=cfg["question"])
    return tok.apply_chat_template([{"role": "system", "content": cfg["system"]}, {"role": "user", "content": user}],
                                   tokenize=False, add_generation_prompt=True, enable_thinking=False)

rows = [json.loads(l) for l in open(DATA, encoding="utf-8")]
random.Random(7).shuffle(rows)
texts = [prompt(r["src"], r["tgt"]) for r in rows[:256]]
ds = Dataset.from_dict({"text": texts}).map(
    lambda x: tok(x["text"], add_special_tokens=False, truncation=True, max_length=512), remove_columns=["text"])

IGNORE = ["lm_head", "re:.*per_layer.*"]
if SCHEME == "w8a8":
    # no SmoothQuant: llm-compressor has no Gemma 4 mapping, and Gemma's (1 + weight) RMSNorm breaks naive smoothing;
    # W8A8 = int8 weights (GPTQ) + dynamic per-token int8 activations
    recipe = [GPTQModifier(targets="Linear", scheme="W8A8", ignore=IGNORE)]
elif SCHEME == "w4a16":
    recipe = [GPTQModifier(targets="Linear", scheme="W4A16", ignore=IGNORE)]
else:
    sys.exit(f"unknown scheme {SCHEME}")

model = AutoModelForCausalLM.from_pretrained(SRC, dtype="auto", device_map={"": 0})
# pipeline="basic": Gemma 4 E-models share KV across layers, which the default layer-by-layer pipeline cannot run
oneshot(model=model, processor=tok, dataset=ds, recipe=recipe, max_seq_length=512, num_calibration_samples=len(texts),
        pipeline="basic")
model.save_pretrained(OUT, save_compressed=True); tok.save_pretrained(OUT)
shutil.copytree(SRC / "judge_head", OUT / "judge_head", dirs_exist_ok=True)
shutil.copy(SRC / "judge_config.json", OUT / "judge_config.json")
print("saved", OUT)
