"""Bayan meaning judge: P(the Arabic rewrite keeps the meaning of the original), plus three diagnostic heads.

    from judge import MeaningJudge
    j = MeaningJudge("Congi-libya/bayan-meaning-judge-e2b")               # transformers backend
    j = MeaningJudge("Congi-libya/bayan-meaning-judge-e2b", backend="vllm")  # fast batch scoring
    j.score([("original ...", "rewrite ...")])
    # -> [{"same": 0.93, "added": 0.02, "missing": 0.05, "contradict": 0.01, "combined": 0.93}]

Use "same" as the meaning score (reward / gate); the other heads say why a pair fails.
The model is a text-only Gemma 4 E2B; the score is a linear head (judge_head/meaning_head.safetensors) on the final hidden
state of the last prompt token, so any runtime that returns last-token hidden states works.

CLI:  python judge.py MODEL pairs.jsonl out.jsonl [--backend vllm]   (pairs.jsonl rows: {"original","rewrite"})
"""
import argparse, json, os, time
from pathlib import Path

import torch


class MeaningJudge:
    def __init__(self, model, backend="transformers", device="cuda", batch_size=32, gpu_memory_utilization=0.85):
        from huggingface_hub import snapshot_download
        from safetensors.torch import load_file
        from transformers import AutoTokenizer
        self.path = model if os.path.isdir(model) else snapshot_download(model)
        self.cfg = json.load(open(Path(self.path) / "judge_config.json", encoding="utf-8"))
        h = load_file(str(Path(self.path) / "judge_head" / "meaning_head.safetensors"))
        self.W, self.b = h["weight"].float(), h["bias"].float()
        self.tok = AutoTokenizer.from_pretrained(self.path)
        self.backend, self.device, self.bs = backend, device, batch_size
        if backend == "vllm":
            from vllm import LLM
            self.llm = LLM(model=self.path, runner="pooling", max_model_len=4096,
                           gpu_memory_utilization=gpu_memory_utilization, enable_prefix_caching=True,
                           pooler_config={"pooling_type": "LAST", "use_activation": False})
        else:
            from transformers import AutoModelForCausalLM
            self.model = AutoModelForCausalLM.from_pretrained(self.path, dtype=torch.bfloat16).to(device).eval()
            self.W, self.b = self.W.to(device), self.b.to(device)

    def prompt(self, original, rewrite):
        user = self.cfg["user_template"].format(original=original, rewrite=rewrite, question=self.cfg["question"])
        msg = [{"role": "system", "content": self.cfg["system"]}, {"role": "user", "content": user}]
        return self.tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)

    @torch.no_grad()
    def _hidden(self, prompts):
        if self.backend == "vllm":
            outs = self.llm.embed(prompts, use_tqdm=False)
            return torch.tensor([o.outputs.embedding for o in outs], dtype=torch.float32)
        ids = [self.tok(p, add_special_tokens=False)["input_ids"] for p in prompts]
        # No padding at all: batch only prompts of identical token length. With transformers 5.17, Gemma 4 returns
        # corrupted hidden states for some rows of a padded batch (left OR right padding, with an attention mask).
        by_len = {}
        for i, s in enumerate(ids):
            by_len.setdefault(len(s), []).append(i)
        res = [None] * len(ids)
        for L, group in by_len.items():
            for k in range(0, len(group), self.bs):
                b = group[k:k + self.bs]
                x = torch.tensor([ids[i] for i in b], device=self.device)
                hs = self.model.model(input_ids=x).last_hidden_state[:, -1].float().cpu()
                for j, i in enumerate(b): res[i] = hs[j]
        return torch.stack(res)

    def score(self, pairs):
        h = self._hidden([self.prompt(o, r) for o, r in pairs])
        p = torch.sigmoid(h.to(self.W.device) @ self.W.T + self.b).cpu()
        out = []
        for q in p.tolist():
            d = dict(zip(self.cfg["heads"], q))
            d["combined"] = min(d["same"], 1 - d["added"], 1 - d["missing"], 1 - d["contradict"])
            out.append(d)
        return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("model"); ap.add_argument("pairs"); ap.add_argument("out")
    ap.add_argument("--backend", default="transformers", choices=["transformers", "vllm"])
    a = ap.parse_args()
    rows = [json.loads(l) for l in open(a.pairs, encoding="utf-8")]
    j = MeaningJudge(a.model, backend=a.backend)
    t = time.time()
    res = j.score([(r.get("original"), r.get("rewrite", r.get("candidate"))) for r in rows])
    sec = time.time() - t
    with open(a.out, "w") as f:
        for r, s in zip(rows, res):
            f.write(json.dumps({"id": r.get("id"), **s}) + "\n")
    json.dump({"model": a.model, "backend": a.backend, "pairs_per_sec": len(rows) / sec}, open(a.out + ".meta.json", "w"))
    print(f"{len(rows)} pairs in {sec:.1f}s = {len(rows) / sec:.1f} pairs/s ({a.backend})")
