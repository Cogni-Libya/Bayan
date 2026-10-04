"""Reference outputs for EngineParityTest: transformers' generate (4.57.6, through optimum's ONNX Runtime wrapper) on a
model bundle's int8 encoder and decoder, one sentence at a time, greedy and with 4 beams.

    python tools/beam_reference.py BUNDLE OPTIMUM_DIR PIECES OUT [IDS]

BUNDLE       a model bundle (bayan_model.json, tokenizer.json, encoder.onnx, decoder.onnx)
OPTIMUM_DIR  the same model laid out for optimum: encoder_model.onnx and decoder_model_merged.onnx (links to the
             bundle's files), and the model's config.json and generation_config.json
PIECES       lines of {"k", "text"}
OUT          lines of {"k", "input_ids", "b1", "b4", ...}: the parity test reads "input_ids" and "b4"
IDS          optional: lines of {"k", "input_ids"} (e.g. from the phone) to decode exactly those inputs
"""
import json, sys, time
import torch
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from tokenizers import Tokenizer

bundle, optimum_dir, pieces, out_path = sys.argv[1:5]
given = {}
if len(sys.argv) > 5:
    for l in open(sys.argv[5], encoding="utf-8"):
        r = json.loads(l); given[r["k"]] = r["input_ids"]
spec = json.load(open(f"{bundle}/bayan_model.json"))
tok = Tokenizer.from_file(f"{bundle}/tokenizer.json")
model = ORTModelForSeq2SeqLM.from_pretrained(optimum_dir, use_cache=True)
with open(out_path, "w", encoding="utf-8") as f, torch.no_grad():
    for l in open(pieces, encoding="utf-8"):
        r = json.loads(l)
        ids = given.get(r["k"]) or tok.encode(spec["prefix"] + r["text"]).ids[: spec["max_input_tokens"]]
        x = torch.tensor([ids])
        rec = {"k": r["k"], "input_ids": ids}
        for beams in (1, 4):
            t = time.time()
            g = model.generate(input_ids=x, attention_mask=torch.ones_like(x), num_beams=beams, do_sample=False,
                               max_length=spec["max_output_tokens"], no_repeat_ngram_size=spec["no_repeat_ngram_size"])
            rec[f"b{beams}"] = g[0].tolist()
            rec[f"b{beams}_text"] = tok.decode(g[0].tolist(), skip_special_tokens=True)
            rec[f"b{beams}_ms"] = (time.time() - t) * 1000
        f.write(json.dumps(rec, ensure_ascii=False) + "\n"); f.flush()
