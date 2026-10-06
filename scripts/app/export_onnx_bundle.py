"""Turn a seq2seq checkpoint into the Android app's model bundle, exactly as the shipped model 2 bundles were made,
and check the int8 bundle against PyTorch with the same greedy loop the app runs (Seq2SeqEngine.kt).

Steps: Optimum export to ONNX with KV cache (merged decoder), int8 dynamic quantization of MatMul and Gather (per
channel), then bayan_model.json, the settings the Kotlin engine reads. No vocabulary pruning: the shipped AraT5v2
bundle is about 450 MB, the AraBART one about 212 MB.

    python export_onnx_bundle.py arat5   Congi-libya/bayan-model2-arat5   "بسّط: "
    python export_onnx_bundle.py arabart Congi-libya/bayan-model2-arabart "بسط: "
    python export_onnx_bundle.py model3  <repo or local dir> "بسط: " --check items.jsonl

The model is a Hugging Face repo or a local checkpoint. --check takes a JSONL with a "source" field (or one sentence
per line) to compare on; without it the three sentences below are used. Output: bundle_<name>/{encoder.onnx,
decoder.onnx, tokenizer.json, bayan_model.json}.

Environment the shipped bundles were made with: transformers 4.46.3, optimum 1.23.3, onnx 1.20.1,
onnxruntime 1.23.0, torch 2.5.1 (CPU). Use transformers < 5: under 5, AraT5's tied weights and AraBART's
special tokens change, and the outputs no longer match.
"""
import argparse, json, shutil, subprocess, sys, time
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from onnxruntime.quantization import QuantType, quantize_dynamic
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

CHECKS = ["تغير العلم الأفغاني عدة مرات خلال هذا القرن، خاصة فيما يتعلق بالشعار الموجود في العلم.",
          "وعلى الرغم من الصعوبات الجمة التي اعترضت سبيل البعثة، فقد تمكن أعضاؤها من بلوغ القمة في اليوم الثالث.",
          "يعد الاحتباس الحراري من أبرز التحديات التي تواجه البشرية، إذ يؤدي إلى ارتفاع منسوب مياه البحار."]

ap = argparse.ArgumentParser()
ap.add_argument("name"); ap.add_argument("model"); ap.add_argument("prefix")
ap.add_argument("--check", help="JSONL with a 'source' field, or plain text, one sentence per line")
ap.add_argument("--n", type=int, default=12, help="how many --check sentences to compare")
args = ap.parse_args()
name, repo, prefix = args.name, args.model, args.prefix
fp32, out = Path(f"{name}-fp32"), Path(f"bundle_{name}")
out.mkdir(exist_ok=True)

if not (fp32 / "decoder_model_merged.onnx").exists():
    subprocess.run([str(Path(sys.executable).parent / "optimum-cli"), "export", "onnx", "--model", repo,
                    "--task", "text2text-generation-with-past", str(fp32)], check=True)

for part, dst in (("encoder_model.onnx", "encoder.onnx"), ("decoder_model_merged.onnx", "decoder.onnx")):
    if not (out / dst).exists():
        t = time.time()
        quantize_dynamic(str(fp32 / part), str(out / dst), weight_type=QuantType.QInt8, per_channel=True,
                         op_types_to_quantize=["MatMul", "Gather"], extra_options={"EnableSubgraph": True})
        print(f"{dst}: {(out / dst).stat().st_size / 1e6:.0f} MB ({time.time() - t:.0f}s)")

tok = AutoTokenizer.from_pretrained(repo)
if (fp32 / "tokenizer.json").exists():
    shutil.copy(fp32 / "tokenizer.json", out / "tokenizer.json")
else:
    tok.backend_tokenizer.save(str(out / "tokenizer.json"))
cfg = json.load(open(fp32 / "config.json"))
dec = onnx.load(str(out / "decoder.onnx"), load_external_data=False)
past = [i.name for i in dec.graph.input if i.name.startswith("past_key_values")]
n_layers = len({p.split(".")[1] for p in past})
heads = cfg.get("decoder_attention_heads") or cfg.get("num_heads")
head_dim = cfg.get("d_kv") or cfg["d_model"] // heads
meta = {
    "id": name, "hf_repo": repo, "prefix": prefix,
    "decoder_start_token_id": cfg["decoder_start_token_id"], "eos_token_id": cfg["eos_token_id"],
    "pad_token_id": cfg["pad_token_id"], "num_layers": n_layers, "num_heads": heads, "head_dim": head_dim,
    "max_input_tokens": 256, "max_output_tokens": 256, "no_repeat_ngram_size": 3,
    "encoder_inputs": [i.name for i in onnx.load(str(out / "encoder.onnx"), load_external_data=False).graph.input],
    "decoder_inputs": [i.name for i in dec.graph.input], "decoder_outputs": [o.name for o in dec.graph.output],
}
json.dump(meta, open(out / "bayan_model.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps({k: v for k, v in meta.items() if "puts" not in k}, ensure_ascii=False))

enc = ort.InferenceSession(str(out / "encoder.onnx"), providers=["CPUExecutionProvider"])
decs = ort.InferenceSession(str(out / "decoder.onnx"), providers=["CPUExecutionProvider"])


def banned(seq, n):
    if len(seq) < n: return set()
    tail = tuple(seq[-(n - 1):])
    return {seq[i + n - 1] for i in range(len(seq) - n + 1) if tuple(seq[i:i + n - 1]) == tail}


def onnx_greedy(text):
    ids = tok(prefix + text, return_tensors="np", truncation=True, max_length=256)
    feeds = {"input_ids": ids["input_ids"].astype(np.int64), "attention_mask": ids["attention_mask"].astype(np.int64)}
    hidden = enc.run(None, {k: v for k, v in feeds.items() if k in meta["encoder_inputs"]})[0]
    seq, pkv = [meta["decoder_start_token_id"]], None
    for step in range(256):
        f = {"input_ids": np.array([[seq[-1]]], np.int64), "encoder_attention_mask": feeds["attention_mask"],
             "encoder_hidden_states": hidden, "use_cache_branch": np.array([pkv is not None])}
        for i in range(n_layers):
            for part in ("decoder.key", "decoder.value", "encoder.key", "encoder.value"):
                k = f"past_key_values.{i}.{part}"
                if pkv is None:
                    L = 0 if part.startswith("decoder") else 1
                    f[k] = np.zeros((1, heads, L, head_dim), np.float32)
                else:
                    f[k] = pkv[k]
        outs = dict(zip(meta["decoder_outputs"], decs.run(None, f)))
        logits = outs["logits"][0, -1].copy()
        for b in banned(seq, 3): logits[b] = -1e9
        nxt = int(logits.argmax()); seq.append(nxt)
        new = {k.replace("present", "past_key_values"): v for k, v in outs.items() if k.startswith("present")}
        if pkv is not None:  # the cache branch returns empty encoder tensors; keep the first ones
            for k in new:
                if ".encoder." in k: new[k] = pkv[k]
        pkv = new
        if nxt == meta["eos_token_id"]: break
    return tok.decode(seq, skip_special_tokens=True)


tests = CHECKS
if args.check:
    lines = [l.strip() for l in open(args.check, encoding="utf-8") if l.strip()]
    tests = [json.loads(l)["source"] if l.startswith("{") else l for l in lines]
    tests = tests[::max(1, len(tests) // args.n)][:args.n]
pt = AutoModelForSeq2SeqLM.from_pretrained(repo).eval()
same = 0
for t in tests:
    a = time.time(); o = onnx_greedy(t); dt = time.time() - a
    ref = tok.decode(pt.generate(**tok(prefix + t, return_tensors="pt"), num_beams=1, do_sample=False,
                                 no_repeat_ngram_size=3, max_new_tokens=256)[0], skip_special_tokens=True)
    same += o.strip() == ref.strip()
    print(f"\nSRC {t}\nPT  {ref}\nONX {o}  ({dt:.1f}s)")
print(f"\nint8 ONNX == PyTorch greedy on {same}/{len(tests)}")
