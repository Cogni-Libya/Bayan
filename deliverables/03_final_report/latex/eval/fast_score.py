"""Run scripts/evaluation/score.py unchanged, with its models on the GPU and
per-text results cached (the copy baseline and the buckets re-score the same
strings). Metric code is score.py's own."""
import functools, sys, types
import torch
sys.argv = ["score.py", sys.argv[1]]
path = "scripts/evaluation/score.py"
mod = types.ModuleType("score"); mod.__file__ = path
code = compile(open(path).read().replace('if __name__ == "__main__":', "if False:"), path, "exec")
exec(code, mod.__dict__)
dev = "cuda" if torch.cuda.is_available() else "cpu"
mod._readability_model.to(dev)
tok, model = mod._readability_tokenizer, mod._readability_model
@functools.lru_cache(maxsize=None)
def level(text):
    inputs = tok(mod.strip_diacritics(text), return_tensors="pt", truncation=True).to(dev)
    # identical to score.predict_readability_level, but on `dev`
    with torch.no_grad():
        outputs = model(**inputs)
    probs = torch.softmax(outputs.logits.squeeze(), dim=0)
    levels = torch.arange(1, len(probs) + 1, dtype=torch.float, device=probs.device)
    return (probs * levels).sum().item()
mod.predict_readability_level = level
import bert_score
_bs = bert_score.score
mod.bertscore_score = lambda *a, **k: _bs(*a, **{**k, "device": dev, "batch_size": 64})
mod.main(sys.argv[1])
