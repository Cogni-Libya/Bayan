"""Score one predictions file: every measure of both tiers, per item set, with a 95% interval clustered by document,
and optionally the paired difference against a baseline predictions file on the same items. No composite score.

Judge-tier rates use only items that have an accepted verdict; the rest are counted as pending, never guessed."""
from .data import SETS, item_set
from .measures import CODE, JUDGE, code_measures, judge_tracks
from .stats import ci, paired


def per_item(items, preds, verdicts, lex=None, levels=None):
    """{item id: (item, {code measure: bool/None}, {judge track: bool/None})}"""
    out = {}
    for i, it in items.items():
        o = preds[i]
        flags = verdicts.flags(it["source"], o) if verdicts is not None and it["track"] != "F" else None
        out[i] = (it, code_measures(it, o, lex, levels), judge_tracks(it, o, flags, lex, levels) if verdicts is not None else {})
    return out


def _collect(rows, tier, name, set_name):
    """{item id: (document, passed)} for one measure on one item set, plus the number pending (judge tier)."""
    got, pending = {}, 0
    for i, (it, code, judge) in rows.items():
        if item_set(it) != set_name:
            continue
        v = (code if tier == "code" else judge).get(name, "absent")
        if v == "absent" or (tier == "code" and v is None):
            continue
        if v is None:
            pending += 1
        else:
            got[i] = (it["doc"], v)
    return got, pending


def score(items, preds, verdicts=None, lex=None, levels=None, baseline=None, sets=SETS):
    """Result dict: {set: {"code": {measure: {...}}, "judge": {track: {...}}}}; each entry has rate [%, low, high],
    n (items measured), and for the judge tier pending (items still without a verdict); with a baseline, diff vs it."""
    rows = per_item(items, preds, verdicts, lex, levels)
    base = per_item(items, baseline, verdicts, lex, levels) if baseline is not None else None
    res = {"items": len(items), "sets": {}}
    for s in sets:
        n_items = sum(item_set(it) == s for it in items.values())
        if not n_items:
            continue
        block = {"items": n_items, "code": {}, "judge": {}}
        for tier, names in (("code", CODE), ("judge", JUDGE)):
            for name in names:
                got, pending = _collect(rows, tier, name, s)
                if not got and not pending:
                    continue
                e = {"rate": list(ci(list(got.values()))), "n": len(got)}
                if tier == "judge":
                    e["pending"] = pending
                if base is not None:
                    b, _ = _collect(base, tier, name, s)
                    (d, lo, hi), n = paired(got, b)
                    e["diff"] = [d, lo, hi]; e["diff_n"] = n
                block[tier][name] = e
        res["sets"][s] = block
    return res


def fmt(res, title="", baseline_name=None):
    """The scorecard as text."""
    out = [title] if title else []
    for s, block in res["sets"].items():
        out.append(f"\n== {s} items ({block['items']}) ==")
        for tier, label in (("code", "code tier (deterministic)"), ("judge", "judge tier (accepted judge verdicts only)")):
            if not block[tier]:
                continue
            out.append(f"  {label}")
            for name, e in block[tier].items():
                m, lo, hi = e["rate"]
                cell = f"{m:5.1f} [{lo:3.0f}-{hi:3.0f}]" if m == m else "    —"
                extra = f"n={e['n']}"
                if e.get("pending"):
                    extra += f", pending {e['pending']}"
                if "diff" in e and e["diff"][0] == e["diff"][0]:
                    d, a, b = e["diff"]
                    extra += f", vs {baseline_name or 'baseline'} {d:+.1f} [{a:+.0f},{b:+.0f}]{'*' if a > 0 or b < 0 else ''}"
                label_name = name if tier == "code" else f"{name}: {JUDGE[name]}"
                out.append(f"    {label_name[:62]:62} {cell}  {extra}")
    return "\n".join(out)


def pending_summary(res):
    return {s: sum(e.get("pending", 0) for e in b["judge"].values()) for s, b in res["sets"].items()}
