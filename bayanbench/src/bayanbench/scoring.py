"""Score one predictions file: every v2 measure (measures.py), per item set, with a 95% interval clustered by
document, and optionally the paired difference against a baseline predictions file on the same items.

Meaning measures use only pairs with a score from the official meaning scorer; the rest are counted as pending, never
guessed, and a meaning rate is shown only when at least 90% of its items are scored: which outputs get scored first is
not random (copies of the selection never need the scorer, for one), so a rate over a small scored part would be
biased. "meaning kept" uses the threshold frozen in v2.0 from the human ratings (#48): P(same) >= 0.5.
The joint rate ("meaning kept and simpler") is shown only when asked for (--joint) with its minimum change set.
The v1 judge tier (Gemini verdicts) is an optional extra (--gemini)."""
from .data import SETS, item_set
from .measures import BLOCKS, CONTINUOUS, JOINT, JUDGE, item_measures, judge_tracks
from .stats import ci, paired

COMPLETE = 0.9          # share of items that must be scored before a meaning (or judge-tier) rate is shown
PENDING_BLOCKS = ("meaning", "judge")


def per_item(items, preds, scores=None, lex=None, levels=None, cfg=None, verdicts=None):
    """{item id: (item, {block: {measure: value}})}; with verdicts, a "judge" block holds the v1 judge tracks."""
    out = {}
    for i, it in items.items():
        o = preds[i]
        m = item_measures(it, o, scores, lex, levels, cfg)
        if verdicts is not None and it["track"] != "F":
            m["judge"] = judge_tracks(it, o, verdicts.flags(it["source"], o), lex, levels)
        out[i] = (it, m)
    return out


def _collect(rows, block, name, set_name):
    """{item id: (document, value)} for one measure on one item set, plus how many are pending (meaning, judge)."""
    got, pending = {}, 0
    for i, (it, m) in rows.items():
        if item_set(it) != set_name:
            continue
        v = m.get(block, {}).get(name, "absent")
        if v == "absent" or (v is None and block not in PENDING_BLOCKS):
            continue
        if v is None:
            pending += 1
        else:
            got[i] = (it["doc"], v)
    return got, pending


def _names(block, joint):
    if block == "judge":
        return JUDGE
    names = dict(BLOCKS[block])
    if block == "meaning" and joint:
        names[JOINT] = "meaning kept and simpler: longest clause or reading level improved by the frozen minimum"
    return names


def score(items, preds, scores=None, lex=None, levels=None, baseline=None, sets=SETS, cfg=None, verdicts=None,
          joint=False):
    """{"items", "sets": {set: {"items", block: {measure: {...}}}}}. Each entry: "rate" [%, low, high] or, for
    continuous measures, "mean" [value, low, high]; n (items measured); pending and complete (meaning and judge
    blocks); with a baseline, "diff" (points, or units for means) and diff_n."""
    rows = per_item(items, preds, scores, lex, levels, cfg, verdicts)
    base = per_item(items, baseline, scores, lex, levels, cfg, verdicts) if baseline is not None else None
    blocks = list(BLOCKS) + (["judge"] if verdicts is not None else [])
    res = {"items": len(items), "sets": {}}
    for s in sets:
        n_items = sum(item_set(it) == s for it in items.values())
        if not n_items:
            continue
        out: dict = {"items": n_items}
        for block in blocks:
            out[block] = {}
            for name in _names(block, joint):
                got, pending = _collect(rows, block, name, s)
                if not got and not pending:
                    continue
                cont = name in CONTINUOUS
                e = {("mean" if cont else "rate"): list(ci(list(got.values()), scale=1 if cont else 100)), "n": len(got)}
                if block in PENDING_BLOCKS:
                    e["pending"] = pending
                    e["complete"] = len(got) >= COMPLETE * (len(got) + pending)
                if base is not None:
                    b, _ = _collect(base, block, name, s)
                    (d, lo, hi), n = paired(got, b, scale=1 if cont else 100)
                    e["diff"] = [d, lo, hi]; e["diff_n"] = n
                out[block][name] = e
        res["sets"][s] = out
    return res


LABELS = {"meaning": "meaning (open scorer)", "simpler": "simpler (change from selection to output, mean)",
          "checks": "checks (deterministic)", "behaviour": "behaviour tests (outside the headline)",
          "flags": "flags (sent to the scorer's contradict question; not failures)",
          "diagnostics": "diagnostics (v1 measures under test)", "judge": "v1 judge tier (Gemini verdicts)"}


def fmt(res, title="", baseline_name=None, notes=()):
    """The scorecard as text."""
    out = [title] if title else []
    out += [f"  note: {n}" for n in notes]
    for s, block in res["sets"].items():
        out.append(f"\n== {s} items ({block['items']}) ==")
        for b, label in LABELS.items():
            if not block.get(b):
                continue
            out.append(f"  {label}")
            for name, e in block[b].items():
                cont = "mean" in e
                m, lo, hi = e["mean" if cont else "rate"]
                if m != m:
                    cell = "    —"
                elif cont:
                    cell = f"{m:+6.2f} [{lo:+.2f}, {hi:+.2f}]"
                else:
                    cell = f"{m:5.1f} [{lo:3.0f}-{hi:3.0f}]"
                if b in PENDING_BLOCKS and not e["complete"]:
                    cell = f"incomplete ({e['n']} of {e['n'] + e['pending']} scored)"
                extra = f"n={e['n']}"
                if e.get("pending"):
                    extra += f", pending {e['pending']}"
                if "diff" in e and e["diff"][0] == e["diff"][0]:
                    d, a, z = e["diff"]
                    sig = "*" if a > 0 or z < 0 else ""
                    extra += (f", vs {baseline_name or 'baseline'} {d:+.2f} [{a:+.2f},{z:+.2f}]{sig}" if cont
                              else f", vs {baseline_name or 'baseline'} {d:+.1f} [{a:+.0f},{z:+.0f}]{sig}")
                label_name = f"{name}: {JUDGE[name]}" if b == "judge" else name
                out.append(f"    {label_name[:62]:62} {cell}  {extra}")
    return "\n".join(out)


def pending_summary(res):
    return {s: {b: sum(e.get("pending", 0) for e in blk.get(b, {}).values()) for b in PENDING_BLOCKS if blk.get(b)}
            for s, blk in res["sets"].items()}
