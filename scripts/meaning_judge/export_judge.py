"""Export the fine-tuned 4-head meaning judge as a portable text-only model.

Gemma 4 E2B (multimodal) + LoRA adapter + 4 linear heads  ->  OUT/
    config.json, model*.safetensors   plain Gemma4ForCausalLM (text only, LoRA merged), loadable by any tool
    tokenizer files (+ chat template)
    judge_head/meaning_head.safetensors  weight [4, hidden], bias [4]; rows = same, added, missing, contradict
    judge_config.json                 prompt pieces + head names

Checks, on real bench prompts, that the exported model reproduces the training-time head scores.
  python export_judge.py runs/e2b_mh export/bayan-meaning-judge-e2b
"""
import json, sys
from pathlib import Path

import torch
from peft import PeftModel
from safetensors.torch import save_file
from transformers import AutoModelForCausalLM, AutoTokenizer, Gemma4ForCausalLM

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS
from paths import BENCH, BENCH_DIR, VERIFIER_DATA

RUN, OUT = Path(sys.argv[1]), Path(sys.argv[2])
BASE = "google/gemma-4-E2B-it"
HEADS = ["same", "added", "missing", "contradict"]
SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
       "difficulty. Answer with a single word: Yes or No.")
OUT.mkdir(parents=True, exist_ok=True)
tok = AutoTokenizer.from_pretrained(BASE)

def prompt(src, tgt):
    user = f"Original:\n{src}\n\nRewrite:\n{tgt}\n\nQuestion: {QUESTIONS['same']}\nAnswer Yes or No."
    return tok.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                                   tokenize=False, add_generation_prompt=True, enable_thinking=False)

bench = [json.loads(l) for l in open(BENCH, encoding="utf-8")][:: 180][:16]
texts = [prompt(r["original"], r["candidate"]) for r in bench]
head = torch.nn.Linear(1536, 4)
sd = torch.load(RUN / "heads.pt", map_location="cpu")
head = torch.nn.Linear(sd["weight"].shape[1], 4); head.load_state_dict(sd); head = head.cuda().float()

@torch.no_grad()
def last_hidden(model, texts, hidden_fn):
    out = []
    for t in texts:   # one at a time: no padding, so the last position is the last real token
        ids = tok(t, add_special_tokens=False, return_tensors="pt")["input_ids"].cuda()
        out.append(hidden_fn(model, ids)[0, -1].float())
    return torch.stack(out)

# 1) reference: the training-time path (multimodal wrapper + LoRA, hidden_states[-1])
mm = AutoModelForCausalLM.from_pretrained(BASE, dtype=torch.bfloat16, device_map={"": 0})
mm = PeftModel.from_pretrained(mm, str(RUN / "adapter"))
ref = last_hidden(mm, texts, lambda m, ids: m(input_ids=ids, output_hidden_states=True).hidden_states[-1])
ref_scores = torch.sigmoid(head(ref))
mm = mm.merge_and_unload()

# 2) text-only model with the merged weights
sdict = {k.replace("model.language_model.", "model."): v for k, v in mm.state_dict().items()
         if k.startswith("model.language_model.")}
tcfg = mm.config.get_text_config()
tcfg.architectures = ["Gemma4ForCausalLM"]
del mm; torch.cuda.empty_cache()
tm = Gemma4ForCausalLM(tcfg).to(torch.bfloat16)
missing, unexpected = tm.load_state_dict(sdict, strict=False)
missing = [k for k in missing if k != "lm_head.weight"]   # tied to the input embeddings
print("missing:", missing[:5], len(missing), "| unexpected:", unexpected[:5], len(unexpected))
assert not missing and not unexpected, "weight mapping mismatch"
tm.tie_weights(); tm = tm.cuda().eval()
new = last_hidden(tm, texts, lambda m, ids: m.model(input_ids=ids).last_hidden_state)
new_scores = torch.sigmoid(head(new))
diff = (new_scores - ref_scores).abs().max().item()
print("max |score diff| exported vs training path:", round(diff, 5))
for r, a, b in list(zip(bench, ref_scores[:, 0].tolist(), new_scores[:, 0].tolist()))[:6]:
    print(f"  {r['id']:>10s} {r['label']:8s} ref {a:.4f}  exported {b:.4f}")
assert diff < 0.02, "exported model does not reproduce the training-time scores"

# 3) save
tm.save_pretrained(OUT, safe_serialization=True); tok.save_pretrained(OUT); (OUT / "judge_head").mkdir(exist_ok=True)
save_file({"weight": head.weight.detach().cpu().contiguous(), "bias": head.bias.detach().cpu().contiguous()},
          str(OUT / "judge_head" / "meaning_head.safetensors"))
json.dump({"heads": HEADS, "system": SYS, "question": QUESTIONS["same"],
           "user_template": "Original:\n{original}\n\nRewrite:\n{rewrite}\n\nQuestion: {question}\nAnswer Yes or No.",
           "combined": "min(same, 1 - added, 1 - missing, 1 - contradict)", "recommended_score": "same",
           "enable_thinking": False, "base_model": BASE},
          open(OUT / "judge_config.json", "w"), ensure_ascii=False, indent=1)
print("saved to", OUT)
