"""Meaning preservation, scored by an open model run locally (BayanBench v2, #47/#48).

The scorer is Gemma 4 31B (google/gemma-4-31B-it-qat-w4a16-ct, int4) in scoring mode: yes/no questions about a
(selection, output) pair, P(yes) read from a single forward pass, no generated text. The prompt is the one the meaning
judge's teacher labels were made with (scripts/meaning_judge/label_teacher.py), so scores from either are the same
scores. P(yes) = P("yes") / (P("yes") + P("no")) over the top-20 first tokens.

Scores are shared data, like the v1 verdicts: one record per (selection, output) pair in meaning/*.jsonl of the data
repo, looked up by content (text.key of the two texts). Scoring reads them and never needs the model, so it runs on
any laptop; an output nobody has scored yet is reported as pending. Whoever has a GPU with 44 GB or more (the model
does not load on 24 GB) runs `bayanbench meaning-pending` and `bayanbench meaning`, then uploads the new records.

Record: {"source", "prediction", "same", "added", "missing", "contradict", "scorer"}. Records in the data repo may
leave out "scorer"; they count as the official scorer's."""
import json
import math
import time
from pathlib import Path

from .data import manifest, read_jsonl
from .text import key, norm

MODEL = "google/gemma-4-31B-it-qat-w4a16-ct"
PROMPT_VERSION = "q-v1"
SYS = ("You compare an Arabic original text with a rewrite of it. Judge meaning only, not style or "
       "difficulty. Answer with a single word: Yes or No.")
QUESTIONS = {
    "same": "Does the rewrite keep exactly the same meaning as the original: every fact, claim and qualifier "
            "preserved, and nothing added, removed, negated or changed? Rephrasing, simpler words and splitting "
            "into shorter sentences are allowed.",
    "added": "Does the rewrite state any fact, detail or claim that the original does not state?",
    "missing": "Is any fact, detail or qualifier from the original missing from the rewrite?",
    "contradict": "Does the rewrite contradict the original or reverse any of its claims (for example a negation, "
                  "a different number, swapped roles, or a statement turned into a question)?",
}
COPY = {"same": 1.0, "added": 0.0, "missing": 0.0, "contradict": 0.0}   # an unchanged selection keeps its meaning


def scorer_name(model=MODEL):
    return f"{model.rsplit('/', 1)[-1]}|{PROMPT_VERSION}"


# Frozen for v2.0 from the human rating round (#48, 3 Oct 2026: 290 tasks, 6 raters; the scorer's AUC against the
# majority "same" is 0.85 [0.79-0.90]): meaning kept = P(same) >= 0.5 and every number kept. The contradiction
# threshold and the joint rule ("meaning kept and simpler") were not decided in v2 and stay unset.
DEFAULT = {"scorer": scorer_name(), "same_threshold": 0.5, "contradict_threshold": None, "simpler_min": None}


def config(d):
    """The meaning settings in the data's manifest.json ("meaning"), over the defaults (v1 data has none)."""
    return {**DEFAULT, **(manifest(d).get("meaning") or {})}


class Scores:
    def __init__(self, d, extra=(), scorer=None):
        """d: benchmark data folder (meaning/*.jsonl); extra: more score files (they must name their scorer)."""
        self.scorer = scorer or config(d)["scorer"]
        self.by_key, self.ignored = {}, 0
        official = sorted((Path(d) / "meaning").glob("*.jsonl"))
        for f, trusted in [(p, True) for p in official] + [(Path(p), False) for p in extra]:
            if not f.exists():
                continue
            for r in read_jsonl(f):
                name = r.get("scorer", self.scorer if trusted else None)
                if name != self.scorer or not isinstance(r.get("same"), (int, float)):
                    self.ignored += 1
                    continue
                self.by_key.setdefault(key(r["source"], r["prediction"]), r)

    def get(self, source, output):
        """{question: P(yes)} for the pair, or None if nobody has scored it yet."""
        if norm(output) == norm(source):
            return COPY
        return self.by_key.get(key(source, output))

    def pending(self, items, preds):
        """Pairs without a score: [{"key", "source", "prediction"}], one per distinct pair. Protected text (F) is
        checked exactly and never scored."""
        out = {}
        for i, it in items.items():
            s, o = it["source"], preds[i]
            if it["track"] != "F" and self.get(s, o) is None:
                out.setdefault(key(s, o), {"key": key(s, o), "source": s, "prediction": o})
        return list(out.values())


def _prompt(tok, source, output, question):
    user = f"Original:\n{source}\n\nRewrite:\n{output}\n\nQuestion: {QUESTIONS[question]}\nAnswer Yes or No."
    try:
        return tok.apply_chat_template([{"role": "system", "content": SYS}, {"role": "user", "content": user}],
                                       tokenize=False, add_generation_prompt=True, enable_thinking=False)
    except Exception:           # templates without a system role or without enable_thinking
        return tok.apply_chat_template([{"role": "user", "content": SYS + "\n\n" + user}], tokenize=False,
                                       add_generation_prompt=True)


def _p_yes(output):
    y = n = 0.0
    for lp in output.outputs[0].logprobs[0].values():
        w = (lp.decoded_token or "").strip().lower()
        if w in ("yes", "y"):
            y += math.exp(lp.logprob)
        elif w in ("no", "n"):
            n += math.exp(lp.logprob)
    return y / (y + n) if y + n else 0.5


def run(pairs, out_path, model=MODEL, questions=tuple(QUESTIONS), gpu_util=0.88, chunk=2000, log=print):
    """Score pairs [{"source", "prediction", ...}] not yet in out_path; append one record per pair. Needs the
    [meaning] extra (vLLM) and a GPU with 44 GB or more for the default model."""
    try:
        from vllm import LLM, SamplingParams
    except ImportError:
        raise SystemExit("scoring meaning needs the [meaning] extra (vLLM) and a 44 GB+ GPU: pip install 'bayanbench[meaning]'")
    done = {key(r["source"], r["prediction"]) for r in read_jsonl(out_path)} if Path(out_path).exists() else set()
    todo = [p for p in pairs if key(p["source"], p["prediction"]) not in done]
    log(f"{len(todo)} pairs to score with {model} ({len(pairs) - len(todo)} already in {out_path})")
    if not todo:
        return
    llm = LLM(model=model, max_model_len=4096, gpu_memory_utilization=gpu_util, enable_prefix_caching=True,
              limit_mm_per_prompt={"image": 0, "video": 0, "audio": 0})
    tok, sp = llm.get_tokenizer(), SamplingParams(max_tokens=1, temperature=0, logprobs=20)
    name, t0 = scorer_name(model), time.time()
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "a", encoding="utf-8", newline="\n") as f:
        for k in range(0, len(todo), chunk):             # chunks, so a crash keeps what is done
            part = todo[k:k + chunk]
            prompts = [_prompt(tok, p["source"], p["prediction"], q) for p in part for q in questions]
            outs = iter(llm.generate(prompts, sp, use_tqdm=False))
            for p in part:
                rec = {"source": p["source"], "prediction": p["prediction"]}
                rec.update({q: round(_p_yes(next(outs)), 4) for q in questions})
                rec["scorer"] = name
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            log(f"{k + len(part)}/{len(todo)} pairs [{(k + len(part)) / (time.time() - t0):.1f} pairs/s]")
