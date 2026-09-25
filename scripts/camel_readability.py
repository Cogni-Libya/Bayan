"""CAMeL Lab's BAREC readability model, for the validation module: 19 reading levels per text.

Model: CAMeL-Lab/readability-arabertv02-word-CE (MIT). It expects BAREC's `Word` text variant, which
arabic_word_variant.to_word() produces. Levels 1-11 of the 19 are the pipeline's "easy" band (levels 1-2 of the
5-level scale), so P(easy) is the summed probability of the first 11 classes.

Device, chosen automatically (override with device= / --device / BAYAN_DEVICE=cpu|cuda):
  GPU  torch on CUDA. The Hugging Face model is downloaded once into the Hugging Face cache.
  CPU  onnxruntime, which is about 1.9x faster than torch per text on CPU (measured on 4 cores; outputs agree to
       4e-6 in P(easy)). The first CPU run downloads the model and exports it to ONNX once (about a minute; this is
       what needs torch on CPU-only machines), caching the file in models/camel_readability_arabertv02_word_onnx/
       (git-ignored; override with BAYAN_CAMEL_ONNX_DIR). Later runs load the cached file with onnxruntime and the
       `tokenizers` library only: no transformers, no torch (which saves several seconds of start-up).

    uv run python scripts/camel_readability.py          # first run fetches and caches the model, then scores two examples
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

from arabic_word_variant import to_word

MODEL_ID = "CAMeL-Lab/readability-arabertv02-word-CE"
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = Path(os.environ.get("BAYAN_CAMEL_ONNX_DIR", PROJECT_ROOT / "models" / "camel_readability_arabertv02_word_onnx"))
N_LEVELS = 19
N_EASY_CLASSES = 11  # 19-level classes 1-11 == levels 1-2 of the 5-level scale (BAREC's own 19 -> 5 map)
LEVEL19_TO_5 = np.array([1] * 7 + [2] * 4 + [3] * 2 + [4] * 2 + [5] * 4)
MAX_LENGTH = 128
_EXPORT_CHECK_TEXTS = ["مثال قصير", "جملة أطول قليلا من المثال الأول هنا", "ذهب الولد إلى المدرسة مع أصدقائه في الصباح الباكر"]


def _gpu_may_exist() -> bool:
    """Cheap check that does not import torch, so CPU-only runs from the cache never pay for it."""
    return shutil.which("nvidia-smi") is not None or Path("/proc/driver/nvidia").exists()


def resolve_device(device: str | None = None) -> str:
    device = (device or os.environ.get("BAYAN_DEVICE") or "auto").lower()
    if device not in ("auto", "cpu", "cuda"):
        raise ValueError(f"device must be auto, cpu or cuda, got {device!r}")
    if device == "cpu":
        return "cpu"
    if device == "auto" and not _gpu_may_exist():
        return "cpu"
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if device == "cuda":
        raise RuntimeError("device 'cuda' requested but torch cannot see a GPU (is a CPU-only torch build installed?)")
    print("NVIDIA GPU found but this torch build has no CUDA support: using the CPU (install a CUDA build of torch to use the GPU)")
    return "cpu"


def export_onnx(cache_dir: Path = CACHE_DIR) -> None:
    """One-time: download the model, export it to ONNX (fp32) and verify it against torch. Atomic: a half-finished
    export never becomes the cache."""
    import onnxruntime
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    print(f"first run: exporting {MODEL_ID} to ONNX (one time, needs internet; cached in {cache_dir})", flush=True)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID).eval()
    enc = tokenizer(_EXPORT_CHECK_TEXTS[:2], padding=True, return_tensors="pt")
    names = [n for n in ("input_ids", "attention_mask", "token_type_ids") if n in enc]
    dynamic = {n: {0: "batch", 1: "seq"} for n in names}
    dynamic["logits"] = {0: "batch"}
    cache_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix=cache_dir.name + ".tmp-", dir=cache_dir.parent))
    try:
        onnx_path = tmp / "model_fp32.onnx"
        torch.onnx.export(model, tuple(enc[n] for n in names), str(onnx_path), input_names=names, output_names=["logits"],
                          dynamic_axes=dynamic, opset_version=17, do_constant_folding=True, dynamo=False)
        tokenizer.save_pretrained(str(tmp))
        check = tokenizer(_EXPORT_CHECK_TEXTS, padding=True, return_tensors="pt")
        with torch.inference_mode():
            expected = model(**check).logits.numpy()
        session = onnxruntime.InferenceSession(str(onnx_path), providers=["CPUExecutionProvider"])
        wanted = {i.name for i in session.get_inputs()}
        (got,) = session.run(None, {k: v.numpy().astype(np.int64) for k, v in check.items() if k in wanted})
        worst = float(np.abs(got - expected).max())
        if worst > 1e-3:
            raise RuntimeError(f"ONNX export disagrees with torch (max logit difference {worst:.2e}); not caching it")
        size_mb = onnx_path.stat().st_size / 1e6
        try:
            tmp.rename(cache_dir)
        except OSError:  # another process finished the same export first
            if not (cache_dir / "model_fp32.onnx").exists():
                raise
        print(f"cached {cache_dir / 'model_fp32.onnx'} ({size_mb:.0f} MB, max logit difference vs torch {worst:.1e})", flush=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class CamelReadability:
    def __init__(self, device: str | None = None, cache_dir: Path | str | None = None):
        self.device = resolve_device(device)
        if self.device == "cuda":
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
            self.model = AutoModelForSequenceClassification.from_pretrained(MODEL_ID).to("cuda").eval()
            self._torch = torch
            self.default_batch_size = 32
        else:
            import onnxruntime
            from tokenizers import Tokenizer  # the cached tokenizer.json needs only this, not transformers (and torch)

            cache_dir = Path(cache_dir) if cache_dir else CACHE_DIR
            if not (cache_dir / "model_fp32.onnx").exists():
                export_onnx(cache_dir)
            self.session = onnxruntime.InferenceSession(str(cache_dir / "model_fp32.onnx"), providers=["CPUExecutionProvider"])
            self.tokenizer = Tokenizer.from_file(str(cache_dir / "tokenizer.json"))
            self.tokenizer.enable_truncation(max_length=MAX_LENGTH)
            self.tokenizer.enable_padding(pad_id=self.tokenizer.token_to_id("[PAD]"), pad_token="[PAD]")
            self._input_names = {i.name for i in self.session.get_inputs()}
            self.default_batch_size = 1  # per text: as fast as batching on CPU, and a text's result never depends on its neighbours

    def _logits(self, batch: list[str]) -> np.ndarray:
        if self.device == "cuda":
            enc = self.tokenizer(batch, return_tensors="pt", truncation=True, max_length=MAX_LENGTH, padding=True).to("cuda")
            with self._torch.inference_mode():
                return self.model(**enc).logits.float().cpu().numpy().astype(np.float64)
        encoded = self.tokenizer.encode_batch(batch)
        feeds = {"input_ids": [e.ids for e in encoded], "attention_mask": [e.attention_mask for e in encoded],
                 "token_type_ids": [e.type_ids for e in encoded]}
        (logits,) = self.session.run(None, {k: np.array(v, dtype=np.int64) for k, v in feeds.items() if k in self._input_names})
        return logits.astype(np.float64)

    def predict_probs(self, texts: list[str], batch_size: int | None = None, preprocess: bool = True,
                      show_progress: bool = False) -> np.ndarray:
        """Softmax over the 19 levels, shape (len(texts), 19). `preprocess` converts raw text to the Word variant."""
        batch_size = batch_size or self.default_batch_size
        inputs = [to_word(t) for t in texts] if preprocess else list(texts)
        out = np.zeros((len(inputs), N_LEVELS), dtype=np.float64)
        order = np.argsort([len(t) for t in inputs]) if batch_size > 1 else np.arange(len(inputs))  # similar lengths pad less
        starts = range(0, len(inputs), batch_size)
        if show_progress:
            from tqdm import tqdm

            starts = tqdm(starts, desc="readability", unit="batch")
        for i in starts:
            idx = order[i:i + batch_size]
            logits = self._logits([inputs[j] for j in idx])
            e = np.exp(logits - logits.max(axis=-1, keepdims=True))
            out[idx] = e / e.sum(axis=-1, keepdims=True)
        return out

    @staticmethod
    def p_easy(probs: np.ndarray) -> np.ndarray:
        return probs[:, :N_EASY_CLASSES].sum(axis=-1)

    @staticmethod
    def levels(probs: np.ndarray) -> np.ndarray:
        """5-level scale (BAREC's own 19 -> 5 map) of the most likely 19-level class."""
        return LEVEL19_TO_5[probs.argmax(axis=-1)]

    @staticmethod
    def expected_level(probs: np.ndarray) -> np.ndarray:
        """E[level] = sum_k k * P(level=k), on the native 19-level scale -- a continuous readability
        estimate from the model's full softmax, richer than the argmax (`levels()`) or binary
        P(easy) (`p_easy()`) collapses. Treats the 19 levels as equally-spaced integers, which is an
        assumption (BAREC's levels are ordinal, not verified interval-scaled)."""
        return probs @ np.arange(1, N_LEVELS + 1)


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch and cache the CAMeL readability model, then score two example sentences.")
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    args = parser.parse_args()
    model = CamelReadability(args.device)
    print(f"device: {model.device}")
    examples = ["ذهب الولد إلى المدرسة مع أصدقائه.",
                "استنكر المجتمع الدولي هذا الانتهاك الصارخ للسيادة الوطنية واعتبره تقويضا لمقومات الاستقرار الإقليمي."]
    probs = model.predict_probs(examples)
    for text, p, lvl in zip(examples, model.p_easy(probs), model.levels(probs)):
        print(f"P(easy) {p:.3f}  level {lvl}  {text}")


if __name__ == "__main__":
    main()
