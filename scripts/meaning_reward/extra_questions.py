"""Extra Gemma 4 31B scores for the all-systems comparison: Arabic correctness, easier to read, coherence.

  python extra_questions.py --data bench_data --preds dev:a.jsonl test:b.jsonl ... --out gemma-4-31b_extra.jsonl

Scoring mode as the bench's meaning scorer: one forward pass, P(yes) / (P(yes) + P(no)) from the top-20 logprobs.
  arabic    (text only)        correct, fluent Modern Standard Arabic: no grammar, agreement, spelling or form errors
  simpler   (original + text)  easier to read for a struggling reader than the original
  coherent  (original + text)  every pronoun and reference clear; nothing cut off, garbled or repeated
Outputs equal to their selection are scored once as the original (arabic, coherent); simpler is then 0 by definition.
One record per distinct (source, text): {"source", "prediction", "arabic", "simpler", "coherent", "scorer"}.
"""
import argparse, json, re, time
from pathlib import Path

from bayanbench.meaning import MODEL, _p_yes
from bayanbench.text import key, norm

QA = ("You are an expert editor of Modern Standard Arabic. Answer with a single word: Yes or No.",
      "Text:\n{output}\n\nQuestion: Is this text correct, fluent Modern Standard Arabic, with no grammar, agreement, "
      "spelling or word-form errors? Answer Yes or No.")
QS = ("You compare an Arabic original text with a rewrite of it. Judge reading difficulty for a struggling (dyslexic) "
      "reader, not meaning. Answer with a single word: Yes or No.",
      "Original:\n{source}\n\nRewrite:\n{output}\n\nQuestion: Is the rewrite easier to read than the original, for "
      "example through shorter sentences, simpler words or simpler structure? Answer Yes or No.")
QC = ("You compare an Arabic original text with a rewrite of it. Judge clarity only. Answer with a single word: Yes or No.",
      "Original:\n{source}\n\nRewrite:\n{output}\n\nQuestion: Is the rewrite clear and coherent on its own: every pronoun "
      "and reference is clear, and no sentence is cut off, garbled or repeated? Answer Yes or No.")

ap = argparse.ArgumentParser()
ap.add_argument("--data")
ap.add_argument("--preds", nargs="+", default=[], help="SPLIT:path pairs (bench outputs)")
ap.add_argument("--pairs", help="jsonl of {source, prediction}: score these as they are")
ap.add_argument("--out", required=True)
ap.add_argument("--model", default=MODEL)
ap.add_argument("--gpu-util", type=float, default=0.88)
ap.add_argument("--chunk", type=int, default=2000)
a = ap.parse_args()

pairs = {}
for sp in a.preds:
    split, path = sp.split(":", 1)
    items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(a.data) / "items" / f"{split}.jsonl", encoding="utf-8")}
    for l in open(path, encoding="utf-8"):
        p = json.loads(l); it = items.get(p["id"])
        if not it or it.get("track") == "F": continue
        s = it["source"]; o = p.get("output") or p.get("prediction")
        pairs.setdefault(key(s, s), (s, s))                     # the original itself (for copies)
        if norm(o) != norm(s): pairs.setdefault(key(s, o), (s, o))
if a.pairs:
    for l in open(a.pairs, encoding="utf-8"):
        r = json.loads(l); s, o = r["source"], r["prediction"]
        pairs.setdefault(key(s, o), (s, o))
done = set()
if Path(a.out).exists():
    done = {key(json.loads(l)["source"], json.loads(l)["prediction"]) for l in open(a.out, encoding="utf-8")}
todo = [(k, s, o) for k, (s, o) in pairs.items() if k not in done]
print(f"{len(pairs)} distinct texts, {len(todo)} to score", flush=True)

from vllm import LLM, SamplingParams  # noqa: E402
llm = LLM(model=a.model, max_model_len=4096, gpu_memory_utilization=a.gpu_util, enable_prefix_caching=True,
          limit_mm_per_prompt={"image": 0, "video": 0, "audio": 0})
tok, sp = llm.get_tokenizer(), SamplingParams(max_tokens=1, temperature=0, logprobs=20)


def prompt(q, s, o):
    sys_, user = q
    msgs = [{"role": "system", "content": sys_}, {"role": "user", "content": user.format(source=s, output=o)}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


t0 = time.time()
with open(a.out, "a", encoding="utf-8") as f:
    for k in range(0, len(todo), a.chunk):
        part = todo[k:k + a.chunk]
        prompts = []
        for _, s, o in part:
            prompts.append(prompt(QA, s, o))
            if o != s: prompts += [prompt(QS, s, o), prompt(QC, s, o)]
            else: prompts += [prompt(QC, s, o)]
        outs = iter(llm.generate(prompts, sp, use_tqdm=False))
        for _, s, o in part:
            rec = {"source": s, "prediction": o, "arabic": round(_p_yes(next(outs)), 4)}
            if o != s: rec["simpler"] = round(_p_yes(next(outs)), 4)
            else: rec["simpler"] = 0.0
            rec["coherent"] = round(_p_yes(next(outs)), 4)
            rec["scorer"] = a.model.rsplit("/", 1)[-1] + "|extra-v1"
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        f.flush()
        print(f"{k + len(part)}/{len(todo)} texts [{(k + len(part)) / (time.time() - t0):.1f}/s]", flush=True)
print("EXTRA_SCORED", flush=True)
