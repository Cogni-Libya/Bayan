"""Judge verdicts as shared data.

A verdict belongs to one (selection, output) pair, keyed by content (text.key), and records which judge gave it and
with which prompt. Scoring reads verdicts, it never calls a judge: an output someone has already had judged scores
at once, an output nobody has judged yet is reported as pending. Only verdicts from the judges accepted in
manifest.json count, so every score on the leaderboard comes from the same, validated judge.

Record: {"key", "source", "prediction", "judge": {"errors": [{"type", "severity", "evidence"}], ...},
         "judge_id": "<backend>:<model>", "prompt": "v2"}"""
from pathlib import Path

from .data import manifest, read_jsonl
from .text import key, norm

MEANING = {"insertion", "deletion", "substitution"}
LANGUAGE = {"grammar", "punctuation"}


def judge_name(rec):
    return f'{rec.get("judge_id")}|{rec.get("prompt")}'


class Verdicts:
    def __init__(self, d, extra=(), accepted=None):
        """d: benchmark data folder (verdicts/*.jsonl); extra: more verdict files (e.g. ones you judged yourself);
        accepted: judge names to trust, default manifest.json's accepted_judges."""
        self.accepted = set(accepted or manifest(d)["accepted_judges"])
        self.by_key, self.ignored = {}, 0
        for f in sorted((Path(d) / "verdicts").glob("*.jsonl")) + [Path(p) for p in extra]:
            if not Path(f).exists():
                continue
            for r in read_jsonl(f):
                if judge_name(r) in self.accepted and isinstance(r.get("judge"), dict):
                    self.by_key.setdefault(r["key"], r)
                else:
                    self.ignored += 1

    def flags(self, source, output):
        """(meaning major?, language major?) or None if no accepted judge has seen this pair. An output identical to
        its source (after normalisation) needs no judge: a copy cannot change the meaning."""
        if norm(output) == norm(source):
            return False, False
        r = self.by_key.get(key(source, output))
        if r is None:
            return None
        major = {e.get("type") for e in r["judge"].get("errors", []) if isinstance(e, dict) and e.get("severity") == "major"}
        return bool(major & MEANING), bool(major & LANGUAGE)

    def pending(self, items, preds):
        """Pairs no accepted judge has seen: [{"key", "source", "prediction"}], one per distinct pair."""
        out = {}
        for i, it in items.items():
            if it["track"] == "F":                 # protected text is checked exactly, never judged
                continue
            s, o = it["source"], preds[i]
            if self.flags(s, o) is None:
                out.setdefault(key(s, o), {"key": key(s, o), "source": s, "prediction": o})
        return list(out.values())
