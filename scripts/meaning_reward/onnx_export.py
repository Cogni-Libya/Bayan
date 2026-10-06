"""Export a seq2seq simplifier to ONNX (encoder + decoder with KV cache) and quantize it to int8 (dynamic, weights).

  python onnx_export.py --model Congi-libya/BayanSimplify-v0.3 --out onnx/v0.3

Writes OUT/fp32 and OUT/int8 (optimum ORTModelForSeq2SeqLM layout, loadable by predict_net.py --backend ort), with
the tokenizer, and prints the file sizes. This is our own export, not the app's bundle script: no vocabulary pruning,
so sizes are an upper bound and outputs may differ slightly from the app's bundle.
"""
import argparse, os, shutil, time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()
t0 = time.time(); out = Path(a.out); fp32, int8 = out / "fp32", out / "int8"

from transformers import AutoConfig, AutoTokenizer, T5Tokenizer
try:
    from optimum.onnxruntime import ORTModelForSeq2SeqLM, ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig
except ImportError as e:
    raise SystemExit(f"optimum[onnxruntime] missing: {e}")

cfg = AutoConfig.from_pretrained(a.model)
tok = T5Tokenizer.from_pretrained(a.model, legacy=True) if cfg.model_type in ("t5", "mt5") else AutoTokenizer.from_pretrained(a.model)
m = ORTModelForSeq2SeqLM.from_pretrained(a.model, export=True, use_cache=True)
m.save_pretrained(fp32); tok.save_pretrained(fp32)
print(f"exported fp32 [{time.time() - t0:.0f}s]:", sorted(p.name for p in fp32.glob("*.onnx")), flush=True)

int8.mkdir(parents=True, exist_ok=True)
qcfg = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)
for f in sorted(fp32.glob("*.onnx")):
    ORTQuantizer.from_pretrained(fp32, file_name=f.name).quantize(save_dir=int8, quantization_config=qcfg)
for f in int8.glob("*_quantized.onnx"):
    f.rename(int8 / f.name.replace("_quantized", ""))
for f in fp32.iterdir():
    if f.suffix != ".onnx" and not f.name.endswith(".onnx_data") and f.is_file() and not (int8 / f.name).exists():
        shutil.copy(f, int8 / f.name)
size = lambda d: sum(p.stat().st_size for p in d.iterdir() if p.is_file()) / 1e6
print(f"int8 done [{time.time() - t0:.0f}s]: fp32 {size(fp32):.0f} MB, int8 {size(int8):.0f} MB;", sorted(p.name for p in int8.glob("*.onnx")), flush=True)
print("ONNX_EXPORT_DONE", flush=True)
