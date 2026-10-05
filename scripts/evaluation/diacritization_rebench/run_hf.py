"""Run a Hugging Face diacritizer (MARBERT+CRF Tashkeel-v3/v4 via its own .diacritize) on the CATT fixture and the
300 BayanBench texts.   python run_hf.py MODEL_ID OUTNAME"""
import json, re, sys, time
from pathlib import Path
import torch
from transformers import AutoModel, AutoTokenizer
H = Path(__file__).parent
MARKS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰ"
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
inputs = [re.sub(f"[{MARKS}]", "", x) for x in gold]
bench = json.load(open(H / "bayan_texts.json", encoding="utf-8"))
mid, name = sys.argv[1], sys.argv[2]
tok = AutoTokenizer.from_pretrained(mid, trust_remote_code=True)
model = AutoModel.from_pretrained(mid, trust_remote_code=True)
dev = torch.device("cuda" if torch.cuda.is_available() else "cpu"); model.to(dev).eval()
with torch.no_grad():
    model.diacritize("بسم الله", tokenizer=tok, device=dev)
    t = time.perf_counter(); out = [model.diacritize(x, tokenizer=tok, device=dev).replace("\n", " ") for x in inputs]; secs = time.perf_counter() - t
    bout = [model.diacritize(x, tokenizer=tok, device=dev) for x in bench]
params = sum(p.numel() for p in model.parameters())
json.dump({"model": name, "seconds": secs, "device": str(dev), "params": params, "outputs": out, "bayan": bout},
          open(H / "out" / f"{name}.json", "w"), ensure_ascii=False)
print(name, f"{secs:.1f}s on {dev}, {params/1e6:.0f}M params", flush=True)
