"""Sequence-level reward for training the simplifier: meaning kept AND simpler, or unchanged when it should be.

For a `generated`-type source (a hard sentence that should be simplified):
    gates    every number in the source appears in the output; corpus v1's structure gates hold (MCQ options in
             order, honorifics, quoted verses: corpus_constraints.structure_gates). Any failure -> reward 0.
    meaning  m = the meaning judge's P(same) (Congi-libya/bayan-meaning-judge-e2b, served by vLLM, see serve_judge.sh)
    simpler  s = clip(lead / LEAD_TARGET, 0, 1), lead = CAMeL expected level of the source (MCQ stem) minus that of
             the output's hardest sentence: corpus v1's readability gate, with 2.0 levels = full credit.
    reward   m * s           (both are needed: a copy has s = 0, a meaning change has m ~ 0)
             or, with meaning_gate=tau:  s if m >= tau else 0   (meaning cannot be traded for simplicity)
For an `identity` / `protected` / `short` source (should be left alone): reward 1 if the output equals the source
(whitespace-normalised), else 0.

The judge is the TRAINING reward only. The bench (BayanBench v2, #48) grades with Gemma 4 31B and human raters.
"""
from __future__ import annotations

import json, os, re, sys
from pathlib import Path

import numpy as np
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))               # scripts/: camel_readability, arabic_word_variant
from corpus_constraints import mcq_stem, readability_units, structure_gates, strip_tashkeel  # noqa: E402

LEAD_TARGET = 2.0
KEEP_TYPES = {"identity", "protected", "short"}
DIGITS = re.compile(r"[0-9٠-٩۰-۹]+")
_TO_ASCII = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def numbers_kept(source: str, output: str) -> bool:
    """Every number of the source appears in the output, at least as many times (digit forms unified)."""
    from collections import Counter
    src = Counter(d.translate(_TO_ASCII) for d in DIGITS.findall(source))
    out = Counter(d.translate(_TO_ASCII) for d in DIGITS.findall(output))
    return all(out[k] >= v for k, v in src.items())


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", strip_tashkeel(t)).strip()


class JudgeClient:
    """Meaning judge over a vLLM pooling server: last-token hidden state -> 4-way linear head (same, added, missing,
    contradict). Prompts are built client-side with the judge's own chat template and config."""

    def __init__(self, url: str, model: str, batch: int = 256):
        from huggingface_hub import hf_hub_download, snapshot_download
        from safetensors.torch import load_file
        from transformers import AutoTokenizer
        self.url, self.model, self.batch = url.rstrip("/"), model, batch
        path = model if os.path.isdir(model) else snapshot_download(model, allow_patterns=[
            "judge_config.json", "judge_head/*", "tokenizer*", "chat_template*", "special_tokens_map.json"])
        self.cfg = json.load(open(Path(path) / "judge_config.json", encoding="utf-8"))
        h = load_file(str(Path(path) / "judge_head" / "meaning_head.safetensors"))
        self.W, self.b = h["weight"].float().numpy(), h["bias"].float().numpy()
        self.tok = AutoTokenizer.from_pretrained(path)

    def prompt(self, original: str, rewrite: str) -> str:
        user = self.cfg["user_template"].format(original=original, rewrite=rewrite, question=self.cfg["question"])
        msg = [{"role": "system", "content": self.cfg["system"]}, {"role": "user", "content": user}]
        return self.tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)

    def _hidden(self, prompts: list[str]) -> np.ndarray:
        out = []
        for k in range(0, len(prompts), self.batch):
            r = requests.post(f"{self.url}/pooling", json={"model": self.model, "input": prompts[k:k + self.batch]},
                              timeout=600)
            r.raise_for_status()
            out += [d["data"] for d in r.json()["data"]]
        return np.asarray(out, dtype=np.float32)

    def score(self, pairs: list[tuple[str, str]]) -> np.ndarray:
        """[N, 4] probabilities: same, added, missing, contradict."""
        if not pairs:
            return np.zeros((0, 4), dtype=np.float32)
        h = self._hidden([self.prompt(o, r) for o, r in pairs])
        return 1 / (1 + np.exp(-(h @ self.W.T + self.b)))


class MeaningSimplicityReward:
    def __init__(self, judge: JudgeClient | None, camel=None, device: str | None = None, meaning_gate: float | None = None):
        if camel is None:
            from camel_readability import CamelReadability
            camel = CamelReadability(device=device)
        self.judge, self.camel, self.meaning_gate = judge, camel, meaning_gate
        self._level_cache: dict[str, float] = {}

    def _levels(self, texts: list[str]) -> dict[str, float]:
        new = sorted({t for t in texts if t not in self._level_cache})
        if new:
            lv = self.camel.expected_level(self.camel.predict_probs(new))
            self._level_cache.update(zip(new, map(float, lv)))
        return {t: self._level_cache[t] for t in texts}

    def __call__(self, sources: list[str], outputs: list[str], pair_types: list[str]) -> tuple[np.ndarray, dict]:
        n = len(sources)
        r = np.zeros(n, dtype=np.float32)
        m = np.full(n, np.nan, dtype=np.float32); lead = np.full(n, np.nan, dtype=np.float32)
        gate = np.ones(n, dtype=bool)
        hard = [i for i in range(n) if pair_types[i] not in KEEP_TYPES]
        for i in range(n):
            if pair_types[i] in KEEP_TYPES:
                r[i] = float(_norm(outputs[i]) == _norm(sources[i]))
        for i in hard:
            gate[i] = numbers_kept(sources[i], outputs[i]) and all(structure_gates(sources[i], outputs[i]).values()) \
                and bool(outputs[i].strip())
        live = [i for i in hard if gate[i]]
        if live:
            units = {i: readability_units(outputs[i]) for i in live}
            lv = self._levels([mcq_stem(sources[i]) for i in live] + [u for i in live for u in units[i]])
            for i in live:
                lead[i] = lv[mcq_stem(sources[i])] - max(lv[u] for u in units[i])
            # skip the judge where the output is no simpler at all (reward is 0 either way)
            judged = [i for i in live if lead[i] > 0]
            if judged and self.judge is not None:
                p = self.judge.score([(sources[i], outputs[i]) for i in judged])
                for i, row in zip(judged, p):
                    m[i] = row[0]
            elif judged:
                for i in judged: m[i] = 1.0          # smoke tests without a judge
            for i in judged:
                s = float(np.clip(lead[i] / LEAD_TARGET, 0, 1))
                r[i] = (s if m[i] >= self.meaning_gate else 0.0) if self.meaning_gate is not None else m[i] * s
        info = {"meaning": m, "lead": lead, "gate": gate}
        return r, info
