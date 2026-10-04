"""Is a new judge good enough to be accepted? Compare its verdicts on judge/validation.jsonl with what is known:
  - planted: outputs the official judge passed, with one error planted by code (number changed, negation dropped,
    quantifier swapped, clause deleted, detail invented; agreement broken, mid-sentence full stop): truth by construction
  - official: outputs the official judge (Gemini 3.1 Pro, v2 checklist) judged: agreement on meaning and on Arabic
The acceptance thresholds are in manifest.json ("judge_acceptance"), fixed before any candidate was tested."""
from pathlib import Path

from .data import manifest, read_jsonl
from .verdicts import LANGUAGE, MEANING

PLANT_MEANING = {"number changed", "negation dropped", "quantifier swapped", "clause deleted", "detail invented"}


def _flags(j):
    m = {e.get("type") for e in (j or {}).get("errors", []) if isinstance(e, dict) and e.get("severity") == "major"}
    return bool(m & MEANING), bool(m & LANGUAGE)


def _agree(pairs):
    """pairs: (official flag, candidate flag) -> recall of the official flags, pass rate on official clean, kappa."""
    tp = sum(a and b for a, b in pairs); fn = sum(a and not b for a, b in pairs)
    tn = sum(not a and not b for a, b in pairs); fp = sum(not a and b for a, b in pairs); n = len(pairs)
    po = (tp + tn) / max(1, n); pe = ((tp + fn) * (tp + fp) + (tn + fp) * (tn + fn)) / max(1, n * n)
    return {"recall": round(tp / max(1, tp + fn), 3), "clean_pass": round(tn / max(1, tn + fp), 3),
            "kappa": round((po - pe) / max(1e-9, 1 - pe), 3), "n": n}


def report(d, verdict_path):
    val = {r["key"]: r for r in read_jsonl(Path(d) / "judge" / "validation.jsonl")}
    got = {r["key"]: _flags(r["judge"]) for r in read_jsonl(verdict_path) if r["key"] in val and isinstance(r.get("judge"), dict)}
    rule = manifest(d)["judge_acceptance"]
    out: dict = {"verdicts": len(got), "of": len(val)}
    for k, idx in (("meaning", 0), ("language", 1)):
        out[f"{k} vs official judge"] = _agree([(val[x]["official"][k], f[idx]) for x, f in got.items() if val[x].get("official")])
    caught = {}
    for x, f in got.items():
        t = val[x].get("planted")
        if t:
            caught.setdefault(t, []).append(f[0] if t in PLANT_MEANING else f[1])
    out["planted caught"] = {t: f"{sum(v)}/{len(v)}" for t, v in sorted(caught.items())}
    pm = [c for t, v in caught.items() if t in PLANT_MEANING for c in v]
    out["planted meaning errors caught"] = round(sum(pm) / max(1, len(pm)), 3)
    mv = out["meaning vs official judge"]
    out["rule"] = {f"meaning recall >= {rule['meaning_recall']}": mv["recall"] >= rule["meaning_recall"],
                   f"meaning clean pass >= {rule['meaning_clean_pass']}": mv["clean_pass"] >= rule["meaning_clean_pass"],
                   f"meaning kappa >= {rule['meaning_kappa']}": mv["kappa"] >= rule["meaning_kappa"],
                   f"planted meaning caught >= {rule['planted_meaning']}": out["planted meaning errors caught"] >= rule["planted_meaning"],
                   f"language recall >= {rule['language_recall']}": out["language vs official judge"]["recall"] >= rule["language_recall"]}
    out["accept"] = all(out["rule"].values())
    return out
