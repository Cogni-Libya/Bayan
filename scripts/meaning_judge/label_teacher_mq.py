"""Label the fine-tune subsample with a teacher LLM in scoring mode for the added / missing / contradict questions
(P(yes) per question in one pass; the three prompts of a pair share their prefix, so vLLM caches it).

Rebuilds exactly the rows train_llm_verifier.py samples (same --data-seed and --n-train / --n-val logic), keeps only
teacher-judged rows (synthetic rows already carry certain 0/1 labels), and writes key -> p to OUT.

  VLLM_ENABLE_V1_MULTIPROCESSING=0 python label_teacher_mq.py google/gemma-4-31B-it-qat-w4a16-ct teacher_gemma31b_mq.jsonl
"""
import json, math, os, random, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from questions import QUESTIONS
from paths import BENCH, BENCH_DIR, VERIFIER_DATA, load_split

model, out = sys.argv[1], Path(sys.argv[2])
N_TRAIN, N_VAL, SEED = 60000, 2000, 13
SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
       "difficulty. Answer with a single word: Yes or No.")
read = lambda p: [json.loads(l) for l in open(p, encoding="utf-8")]

# ---- identical sampling to train_llm_verifier.py ----
random.seed(SEED)
train = load_split("train"); val = load_split("val")
synth = [r for r in train if not r["origin"].startswith("teacher")]
teach = [r for r in train if r["origin"].startswith("teacher")]
random.shuffle(teach)
train = synth + teach[:max(0, N_TRAIN - len(synth))]
random.shuffle(val); val = val[:N_VAL]
todo = {r["key"]: r for r in (val if os.environ.get("ONLY_VAL") else train + val) if r["origin"].startswith("teacher")}
done = {json.loads(l)["key"] for l in open(out)} if out.exists() else set()
QK = ("added", "missing", "contradict")
rows = [r for k, r in todo.items() if k not in done]
print(f"teacher rows {len(todo)}, to label {len(rows)}", flush=True)

from vllm import LLM, SamplingParams
llm = LLM(model=model, max_model_len=4096, gpu_memory_utilization=float(os.environ.get("GPU_UTIL", "0.88")),
          enable_prefix_caching=True, limit_mm_per_prompt={"image": 0, "video": 0, "audio": 0})
tok = llm.get_tokenizer()
def prompt(r, q):
    user = f"Original:\n{r['src']}\n\nRewrite:\n{r['tgt']}\n\nQuestion: {QUESTIONS[q]}\nAnswer Yes or No."
    msg = [{"role": "system", "content": SYS}, {"role": "user", "content": user}]
    try:
        return tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except Exception:
        return tok.apply_chat_template([{"role": "user", "content": SYS + "\n\n" + user}], tokenize=False,
                                       add_generation_prompt=True)
sp = SamplingParams(max_tokens=1, temperature=0, logprobs=20)
t0 = time.time(); miss = 0
with open(out, "a") as f:
    for k in range(0, len(rows), 4000):          # chunks, so a crash keeps what is done
        chunk = rows[k:k + 4000]
        outs = llm.generate([prompt(r, q) for r in chunk for q in QK], sp, use_tqdm=False)
        for j, r in enumerate(chunk):
            rec = {"key": r["key"]}
            for q, o in zip(QK, outs[3 * j:3 * j + 3]):
                y = n = 0.0
                for lp in o.outputs[0].logprobs[0].values():
                    w = (lp.decoded_token or "").strip().lower()
                    if w in ("yes", "y"): y += math.exp(lp.logprob)
                    elif w in ("no", "n"): n += math.exp(lp.logprob)
                if y + n == 0: miss += 1
                rec[q] = y / (y + n) if y + n else 0.5
            f.write(json.dumps(rec) + "\n")
        f.flush()
        el = time.time() - t0
        print(f"{k + len(chunk)}/{len(rows)}  {(k + len(chunk)) / el:.1f} pairs/s", flush=True)
print(f"no yes/no in top-20: {miss}\nEXIT=0", flush=True)
