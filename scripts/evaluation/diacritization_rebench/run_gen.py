"""A generative diacritizer (Etherll/Tashkeel-350M-v2), greedy, with its README prompt, one sentence at a time."""
import json, re, sys, time
from pathlib import Path
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
H = Path(__file__).parent
MARKS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰ"
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
inputs = [re.sub(f"[{MARKS}]", "", x) for x in gold]
bench = json.load(open(H / "bayan_texts.json", encoding="utf-8"))
mid, name = sys.argv[1], sys.argv[2]
tok = AutoTokenizer.from_pretrained(mid)
model = AutoModelForCausalLM.from_pretrained(mid, torch_dtype=torch.bfloat16).to("cuda").eval()
def run(x):
    ids = tok.apply_chat_template([{"role": "user", "content": "قم بتشكيل هذا النص " + ":\n" + x}], add_generation_prompt=True, return_tensors="pt", tokenize=True).to(model.device)
    if not isinstance(ids, torch.Tensor): ids = ids["input_ids"]
    with torch.no_grad():
        out = model.generate(ids, do_sample=False, max_new_tokens=int(len(x) * 2.5) + 32)
    return tok.decode(out[0, ids.shape[-1]:], skip_special_tokens=True).strip().replace("\n", " ")
run("السلام عليكم")
t = time.perf_counter(); out = [run(x) for x in inputs]; secs = time.perf_counter() - t
json.dump({"model": name, "seconds": secs, "outputs": out, "bayan": [run(x) for x in bench]}, open(H / "out" / f"{name}.json", "w"), ensure_ascii=False)
print(name, f"{secs:.0f}s", flush=True)
