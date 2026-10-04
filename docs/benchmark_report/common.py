"""Shared loaders for figures.py and tables.py: the scorecards (build/scores) and build/analysis.json."""
import json, math
from functools import lru_cache
from pathlib import Path

import systems as S

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
SETS = ("core", "held-out", "outside", "written")

# the systems most figures show (all systems are in the full tables)
MAIN = ["copy", "app-arat5", "app-arabart", "model1", "m2-arat5", "m2-arat5-nt", "m2-arabart-nt", "v1-arabart",
        "m3", "m3-net", "m3-b4-net", "m3-dpo-net", "m3-q-b4-net", "rt-net", "rt-q-b4-net"]
SHIP, APP = "m3-q-b4-net", "app-arat5"

GROUP_COLOR = {"reference": "#9e9e9e", "app": "#d62728", "model 1-2": "#ff7f0e", "model 3 family": "#1f77b4",
               "int8": "#2ca02c", "retrain": "#9467bd", "hybrid": "#17becf"}

# (block, measure, short label, kind) kind: rate (%) or mean
MEASURES = [
    ("meaning", "P(same meaning)", "P(same)", "mean"),
    ("meaning", "meaning kept", "Meaning kept", "rate"),
    ("meaning", "meaning kept and simpler", "Kept and simpler", "rate"),
    ("simpler", "longest clause: words shorter", "Clause shorter (words)", "mean"),
    ("simpler", "reading level: levels lower", "Level lower", "mean"),
    ("simpler", "hard words: fewer", "Hard words fewer", "mean"),
    ("checks", "numbers kept", "Numbers kept", "rate"),
    ("checks", "no house-rule break", "No house-rule break", "rate"),
    ("behaviour", "C: easy text left unchanged", "Easy text unchanged", "rate"),
    ("behaviour", "F: letters unchanged", "Protected letters kept", "rate"),
    ("behaviour", "E1: end mark kept", "End mark kept", "rate"),
    ("flags", "negation changed", "Negation changed", "rate"),
    ("flags", "limit changed", "Limit changed", "rate"),
    ("flags", "condition changed", "Condition changed", "rate"),
    ("diagnostics", "kept 60%+ of words", "Kept 60%+ words", "rate"),
    ("diagnostics", "no clause over 15 words", "No clause > 15 words", "rate"),
    ("diagnostics", "mid-sentence full stop added", "Full stop added", "rate"),
    ("diagnostics", "B: not left as copy", "Hard text changed", "rate"),
]
LOWER_BETTER = {"negation changed", "limit changed", "condition changed", "mid-sentence full stop added"}


def label(k):
    return S.SYSTEMS[k][0]


def group(k):
    return S.SYSTEMS[k][1]


def color(k):
    return GROUP_COLOR[group(k)]


@lru_cache(None)
def card(split, key):
    p = BUILD / "scores" / f"{split}__{key}.json"
    return json.load(open(p, encoding="utf-8")) if p.exists() else None


def entry(split, key, block, name, st="core"):
    """The scorecard entry dict, or None."""
    c = card(split, key)
    if not c or st not in c["sets"]:
        return None
    e = c["sets"][st].get(block, {}).get(name)
    if e is None or ("complete" in e and not e["complete"]):
        return None
    return e


def val(split, key, block, name, st="core"):
    """(value, low, high) or (nan,)*3."""
    e = entry(split, key, block, name, st)
    if not e:
        return (math.nan,) * 3
    v = e.get("rate") or e.get("mean")
    return tuple(v)


def diff(split, key, block, name, st="core"):
    e = entry(split, key, block, name, st)
    if not e or "diff" not in e:
        return (math.nan,) * 3
    return tuple(e["diff"])


@lru_cache(None)
def analysis():
    return json.load(open(BUILD / "analysis.json", encoding="utf-8"))


def summ(split, key, st="core"):
    return analysis()["per_system"][split].get(key, {}).get("summary", {}).get(st, {})
