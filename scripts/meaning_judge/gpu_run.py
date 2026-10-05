"""GPU candidates on bench.jsonl. One method per process (frees GPU memory between models).

  python gpu_run.py llm   MODEL OUT     # scoring mode: 4 yes/no questions, P(yes) from one forward pass
  python gpu_run.py xnli  MODEL OUT     # bidirectional entailment
  python gpu_run.py embed MODEL OUT     # cosine similarity
  python gpu_run.py jevembed CONFIG OUT # JevEmbed Noul questions
"""
import json, math, os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS
from paths import BENCH, BENCH_DIR, VERIFIER_DATA

mode, model, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
rows = [json.loads(l) for l in open(BENCH, encoding="utf-8")]
t0 = time.time()
res = [{"id": r["id"]} for r in rows]

if mode == "llm":
    from vllm import LLM, SamplingParams
    llm = LLM(model=model, max_model_len=4096, gpu_memory_utilization=float(os.environ.get("GPU_UTIL", "0.88")), enable_prefix_caching=True)
    tok = llm.get_tokenizer()
    SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
           "difficulty. Answer with a single word: Yes or No.")
    prompts, index = [], []
    for i, r in enumerate(rows):
        for k, q in QUESTIONS.items():
            msg = [{"role": "system", "content": SYS},
                   {"role": "user", "content": f"Original:\n{r['original']}\n\nRewrite:\n{r['candidate']}\n\nQuestion: {q}\nAnswer Yes or No."}]
            try:
                p = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)
            except Exception:   # templates without a system role (Gemma 2 based) or without enable_thinking
                msg = [{"role": "user", "content": SYS + "\n\n" + msg[1]["content"]}]
                p = tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True)
            prompts.append(p); index.append((i, k))
    sp = SamplingParams(max_tokens=1, temperature=0, logprobs=20)
    t1 = time.time()
    outs = llm.generate(prompts, sp)
    gen_sec = time.time() - t1
    miss = 0
    for (i, k), o in zip(index, outs):
        y = n = 0.0
        for lp in o.outputs[0].logprobs[0].values():
            w = (lp.decoded_token or "").strip().lower()
            if w in ("yes", "y"): y += math.exp(lp.logprob)
            elif w in ("no", "n"): n += math.exp(lp.logprob)
        if y + n == 0: miss += 1
        res[i][k] = y / (y + n) if y + n else 0.5
    print("no yes/no token in top-20:", miss, "of", len(outs))
    meta = {"prompts": len(prompts), "forward_sec": gen_sec, "pairs_per_sec": len(rows) / gen_sec}

elif mode == "xnli":
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(model)
    m = AutoModelForSequenceClassification.from_pretrained(model).cuda().half().eval()
    lab = {v.lower(): int(k) for k, v in m.config.id2label.items()}
    E, C = lab["entailment"], lab["contradiction"]

    @torch.no_grad()
    def nli(prem, hyp, bs=64):
        out = []
        for k in range(0, len(prem), bs):
            enc = tok(prem[k:k + bs], hyp[k:k + bs], truncation=True, max_length=512, padding=True, return_tensors="pt").to("cuda")
            out += torch.softmax(m(**enc).logits.float(), -1).cpu().tolist()
        return out
    t1 = time.time()
    fwd = nli([r["original"] for r in rows], [r["candidate"] for r in rows])   # original => rewrite: nothing added
    bwd = nli([r["candidate"] for r in rows], [r["original"] for r in rows])   # rewrite => original: nothing missing
    gen_sec = time.time() - t1
    for x, f, b in zip(res, fwd, bwd):
        x.update(ent_fwd=f[E], ent_bwd=b[E], contra=max(f[C], b[C]))
    meta = {"forward_sec": gen_sec, "pairs_per_sec": len(rows) / gen_sec}

elif mode == "embed":
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer(model, device="cuda", model_kwargs={"torch_dtype": "float16"})
    t1 = time.time()
    a = m.encode([r["original"] for r in rows], batch_size=64, normalize_embeddings=True)
    b = m.encode([r["candidate"] for r in rows], batch_size=64, normalize_embeddings=True)
    gen_sec = time.time() - t1
    for x, u, v in zip(res, a, b):
        x["cos"] = float((u * v).sum())
    meta = {"forward_sec": gen_sec, "pairs_per_sec": len(rows) / gen_sec}

elif mode == "rerank":
    from sentence_transformers import CrossEncoder
    m = CrossEncoder(model, device="cuda", model_kwargs={"torch_dtype": "float16"})
    t1 = time.time()
    fwd = m.predict([(r["original"], r["candidate"]) for r in rows], batch_size=64)   # sigmoid scores
    bwd = m.predict([(r["candidate"], r["original"]) for r in rows], batch_size=64)
    gen_sec = time.time() - t1
    for x, f, b in zip(res, fwd, bwd):
        x.update(fwd=float(f), bwd=float(b))
    meta = {"forward_sec": gen_sec, "pairs_per_sec": len(rows) / gen_sec}

elif mode == "jevembed":
    from jevembed import JevEmbed, ModelConfig
    client = JevEmbed(); cfg = ModelConfig.load(model); client.register(cfg)
    import yaml; mid = yaml.safe_load(open(model))["model_id"]
    if os.environ.get("SMOKE"): n = int(os.environ["SMOKE"]); rows, res = rows[:n], res[:n]
    qs = {k: {"type": "noul", "instructions": q.replace("the rewrite", "`rewrite`").replace("the original", "`original`").replace("The rewrite", "`rewrite`")}
          for k, q in QUESTIONS.items()}
    t1 = time.time()
    for x, r in zip(res, rows):
        ans = client.evaluate({"model": mid, "state": {"original": r["original"], "rewrite": r["candidate"]}, "questions": qs})
        for k, v in ans["answers"].items():
            x[k] = v["noul"]
    gen_sec = time.time() - t1
    meta = {"forward_sec": gen_sec, "pairs_per_sec": len(rows) / gen_sec}

meta.update(mode=mode, model=model, total_sec=time.time() - t0)
with open(out, "w") as f:
    for x in res: f.write(json.dumps(x) + "\n")
json.dump(meta, open(str(out) + ".meta.json", "w"), indent=1)
print(meta, "\nEXIT=0", flush=True)
