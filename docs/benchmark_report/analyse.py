"""Everything the report needs that the scorecards don't hold, computed from the raw files into build/analysis.json:
per-item meaning and simplicity values (with bayanbench's own measures, so they match the scorecards), Gemma extra
scores per system, the scorer-vs-human validation (confusion matrices, ROC, calibration, inter-rater agreement), human
ratings per system, pairwise preferences, training curves and the qualitative examples.

  BAYANBENCH_DATA=<snapshot> python analyse.py      (needs bayanbench v2.0 importable; no GPU, no reading-level model)
"""
import collections, itertools, json, math, re
from pathlib import Path

from bayanbench.data import item_set
from bayanbench.measures import item_measures
from bayanbench.meaning import Scores, config
from bayanbench.stats import ci
from bayanbench.text import longest_clause, norm as bnorm

import systems as S

HERE = Path(__file__).resolve().parent
OUT = HERE / "build"
DI = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
n = lambda t: re.sub(r"\s+", " ", DI.sub("", t)).strip()


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def auc(pos, neg):
    """P(score of a positive > score of a negative), ties half."""
    if not pos or not neg:
        return float("nan")
    s = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank, i, r1 = 0.0, 0, 0.0
    while i < len(s):
        j = i
        while j < len(s) and s[j][0] == s[i][0]:
            j += 1
        avg = (i + j + 1) / 2
        r1 += avg * sum(1 for k in range(i, j) if s[k][1])
        i = j
    return (r1 - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg))


def roc(pos, neg):
    th = sorted(set(pos + neg), reverse=True)
    pts = [(0.0, 0.0)]
    for t in th:
        pts.append((sum(v >= t for v in neg) / len(neg), sum(v >= t for v in pos) / len(pos)))
    return pts


def alpha_nominal(units):
    """Krippendorff's alpha (nominal) for units = [[label, label, ...], ...] (missing omitted)."""
    units = [u for u in units if len(u) >= 2]
    o = collections.Counter()
    for u in units:
        m = len(u)
        for a, b in itertools.permutations(range(m), 2):
            o[(u[a], u[b])] += 1 / (m - 1)
    nc = collections.Counter()
    for (a, b), v in o.items():
        nc[a] += v
    N = sum(nc.values())
    if N <= 1:
        return float("nan")
    do = sum(v for (a, b), v in o.items() if a != b) / N
    de = sum(nc[a] * nc[b] for a in nc for b in nc if a != b) / (N * (N - 1))
    return 1 - do / de if de else float("nan")


def alpha_ordinal(units, order):
    """Krippendorff's alpha with the ordinal (rank) distance."""
    units = [u for u in units if len(u) >= 2]
    o = collections.Counter()
    for u in units:
        m = len(u)
        for a, b in itertools.permutations(range(m), 2):
            o[(u[a], u[b])] += 1 / (m - 1)
    nc = collections.Counter()
    for (a, b), v in o.items():
        nc[a] += v
    N = sum(nc.values())
    idx = {c: i for i, c in enumerate(order)}

    def d(c, k):
        lo, hi = sorted((idx[c], idx[k]))
        s = sum(nc[order[g]] for g in range(lo, hi + 1)) - (nc[c] + nc[k]) / 2
        return s * s
    do = sum(v * d(a, b) for (a, b), v in o.items()) / N
    de = sum(nc[a] * nc[b] * d(a, b) for a in nc for b in nc) / (N * (N - 1))
    return 1 - do / de if de else float("nan")


def kappa(x, y):
    cats = sorted(set(x) | set(y))
    nn = len(x)
    po = sum(a == b for a, b in zip(x, y)) / nn
    pe = sum((x.count(c) / nn) * (y.count(c) / nn) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def main():
    OUT.mkdir(exist_ok=True)
    d = S.BENCH
    cfg = config(d)
    sc = Scores(d, extra=[str(f) for f in S.meaning_files()])
    M4 = {}   # full 4-question records by normalized pair
    for f in S.meaning_files():
        for r in jl(f):
            if "same" in r:
                M4.setdefault((n(r["source"]), n(r["prediction"])), r)
    E = {}
    for f in S.extra_files():
        for r in jl(f):
            if "arabic" in r:
                E.setdefault((n(r["source"]), n(r["prediction"])), r)
    A = {"systems": {k: list(v[:3]) for k, v in S.SYSTEMS.items()}, "per_system": {}, "examples": {}}

    # ---- per system, per split: per-item meaning, extra scores, diagnostics
    for split in ("dev", "test"):
        items = {r["id"]: r for r in jl(d / "items" / f"{split}.jsonl")}
        outs = {k: {r["id"]: r["output"] for r in jl(p)} for k, p in S.outputs(split).items()}
        A["per_system"][split] = {}
        for k, o in outs.items():
            rows = collections.defaultdict(list)
            per_item = {}
            for i, it in items.items():
                out = o.get(i, it["source"])
                m = item_measures(it, out, sc, None, None, cfg)
                st = item_set(it)
                copy = bnorm(out) == bnorm(it["source"])
                rec = {"set": st, "track": it["track"], "copy": copy}
                ps = m["meaning"].get("P(same meaning)")
                if ps is not None and ps != "absent":
                    rec["p_same"] = ps
                key = (n(it["source"]), n(out))
                q = M4.get(key)
                if copy:
                    rec.update(added=0.0, missing=0.0, contradict=0.0)
                elif q:
                    rec.update(added=q["added"], missing=q["missing"], contradict=q["contradict"])
                e = E.get(key)
                if e and it["track"] != "F":
                    rec.update(arabic=e["arabic"], simpler=e["simpler"], coherent=e["coherent"])
                cl = m["simpler"].get("longest clause: words shorter")
                if cl is not None:
                    rec["clause"] = cl
                rec["words_in"], rec["words_out"] = len(it["source"].split()), len(out.split())
                per_item[i] = rec
                rows[st].append((it["doc"], rec))
            summ = {}
            for st, lst in rows.items():
                s = {}
                for f in ("p_same", "added", "missing", "contradict", "arabic", "simpler", "coherent"):
                    xs = [(doc, r[f]) for doc, r in lst if f in r and r["track"] != "F"]
                    if xs:
                        s[f] = list(ci(xs, scale=1)); s[f + "_n"] = len(xs)
                ch = [(doc, r) for doc, r in lst if r["track"] != "F"]
                s["unchanged"] = list(ci([(doc, r["copy"]) for doc, r in ch]))
                chg = [(doc, r["contradict"] >= 0.5) for doc, r in ch if not r["copy"] and "contradict" in r]
                if chg:
                    s["contradict_rate_changed"] = list(ci(chg)); s["changed_scored"] = len(chg)
                ws = [(doc, r["words_out"] / max(r["words_in"], 1)) for doc, r in ch]
                s["length_ratio"] = list(ci(ws, scale=1))
                summ[st] = s
            A["per_system"][split][k] = {"summary": summ,
                                         "items": {i: {kk: vv for kk, vv in r.items() if kk not in ("words_in",)}
                                                   for i, r in per_item.items()}}

    # ---- the scorer vs humans (BayanBench v2 rating round, 3 Oct)
    R = jl(d / "ratings" / "human_ratings_v2.jsonl")
    singles = [r for r in R if r["kind"] == "single"]
    pairs = [r for r in R if r["kind"] == "pair"]
    hv = {}
    lab = [r for r in singles if r["meaning_majority"] in ("same", "minor", "major") and r.get("p_same") is not None]
    pos = [r["p_same"] for r in lab if r["meaning_majority"] == "same"]
    neg = [r["p_same"] for r in lab if r["meaning_majority"] != "same"]
    hv["auc_same"] = auc(pos, neg); hv["n_pos"], hv["n_neg"] = len(pos), len(neg)
    hv["roc_same"] = roc(pos, neg)
    hv["auc_major"] = auc([r["p_same"] for r in lab if r["meaning_majority"] != "major"],
                          [r["p_same"] for r in lab if r["meaning_majority"] == "major"])
    cm = collections.Counter()
    for r in singles:
        if r.get("p_same") is None:
            continue
        cm[(r["meaning_majority"], "kept" if r["p_same"] >= 0.5 else "not kept")] += 1
    hv["confusion_meaning"] = {f"{a}|{b}": v for (a, b), v in cm.items()}
    sweep = []
    for t in [x / 100 for x in range(1, 100)]:
        tp = sum(v >= t for v in pos); tn = sum(v < t for v in neg)
        sweep.append({"t": t, "acc": (tp + tn) / (len(pos) + len(neg)), "tpr": tp / len(pos), "tnr": tn / len(neg),
                      "bal": (tp / len(pos) + tn / len(neg)) / 2})
    hv["sweep"] = sweep
    bins = []
    for lo in [x / 10 for x in range(10)]:
        b = [r for r in lab if lo <= r["p_same"] < lo + 0.1 or (lo == 0.9 and r["p_same"] == 1.0)]
        if b:
            bins.append({"lo": lo, "mean_p": sum(r["p_same"] for r in b) / len(b),
                         "human_same": sum(r["meaning_majority"] == "same" for r in b) / len(b), "n": len(b)})
    hv["calibration"] = bins
    # Gemma extra questions vs humans (Arabic and ease axes, majority of raters)
    def majority(r, axis):
        c = collections.Counter(v.get(axis) for v in r["ratings"].values() if v.get(axis))
        if not c:
            return None
        top = c.most_common()
        return "tie" if len(top) > 1 and top[0][1] == top[1][1] else top[0][0]
    ax = {"arabic": ("a", ["ok", "minor", "major"], "arabic"), "ease": ("e", ["easier", "same", "harder"], "simpler")}
    for name, (axis, order, q) in ax.items():
        c, ps, ns = collections.Counter(), [], []
        for r in singles:
            e = E.get((n(r["source"]), n(r["output"])))
            mj = majority(r, axis)
            if e is None or mj is None:
                continue
            c[(mj, "yes" if e[q] >= 0.5 else "no")] += 1
            if mj in order:
                (ps if mj == order[0] else ns).append(e[q])
        hv[f"confusion_{name}"] = {f"{a}|{b}": v for (a, b), v in c.items()}
        hv[f"auc_{name}"] = auc(ps, ns); hv[f"n_{name}"] = len(ps) + len(ns)
    # inter-rater agreement
    raters = sorted({k for r in singles for k in r["ratings"]})
    hv["raters"] = raters
    hv["alpha"] = {}
    for axis, order in (("m", ["same", "minor", "major"]), ("a", ["ok", "minor", "major"]), ("e", ["easier", "same", "harder"])):
        units = [[v[axis] for v in r["ratings"].values() if v.get(axis) in order] for r in singles]
        hv["alpha"][axis] = {"nominal": alpha_nominal(units), "ordinal": alpha_ordinal(units, order),
                             "units": sum(len(u) >= 2 for u in units)}
        bin_units = [[(x == order[0]) for x in u] for u in units]
        hv["alpha"][axis]["binary"] = alpha_nominal(bin_units)
    pk = {}
    for a_, b_ in itertools.combinations(raters, 2):
        xs, ys = [], []
        for r in singles:
            va, vb = r["ratings"].get(a_, {}).get("m"), r["ratings"].get(b_, {}).get("m")
            if va and vb:
                xs.append(va == "same"); ys.append(vb == "same")
        if len(xs) >= 15:
            pk[f"{a_}|{b_}"] = {"kappa": kappa(xs, ys), "agree": sum(x == y for x, y in zip(xs, ys)) / len(xs), "n": len(xs)}
    hv["pair_kappa"] = pk
    # each rater vs the scorer (kept at 0.5)
    hv["rater_vs_scorer"] = {}
    for rt in raters:
        xs = [(r["ratings"][rt]["m"] == "same", r["p_same"] >= 0.5) for r in singles
              if rt in r["ratings"] and r["ratings"][rt].get("m") and r.get("p_same") is not None]
        if len(xs) >= 15:
            hv["rater_vs_scorer"][rt] = {"agree": sum(a == b for a, b in xs) / len(xs), "kappa": kappa([a for a, _ in xs], [b for _, b in xs]), "n": len(xs)}
    # MiMo second-judge pilot
    mp = S.ROOT / "mimo"
    if (mp / "mimo_pilot.jsonl").exists():
        mm = {r["task"]: r["mimo"] for r in jl(mp / "mimo_pilot.jsonl")}
        c = collections.Counter()
        for r in lab:
            if r["task"] in mm:
                c[(r["meaning_majority"], "kept" if mm[r["task"]] >= 0.5 else "not kept")] += 1
        hv["confusion_mimo"] = {f"{a}|{b}": v for (a, b), v in c.items()}
        hv["mimo_result"] = json.load(open(mp / "mimo_pilot_result.json"))
        mpos = [mm[r["task"]] for r in lab if r["task"] in mm and r["meaning_majority"] == "same"]
        mneg = [mm[r["task"]] for r in lab if r["task"] in mm and r["meaning_majority"] != "same"]
        hv["roc_mimo"] = roc(mpos, mneg); hv["auc_mimo"] = auc(mpos, mneg)
    A["human_validation"] = hv

    # ---- human ratings per system and pairwise preferences
    hs = {}
    for r in singles:
        s = hs.setdefault(r["system"], {"m": collections.Counter(), "a": collections.Counter(), "e": collections.Counter(), "items": 0, "p_same": []})
        s["items"] += 1
        if r.get("p_same") is not None:
            s["p_same"].append(r["p_same"])
        for v in r["ratings"].values():
            for axis in "mae":
                if v.get(axis):
                    s[axis][v[axis]] += 1
    A["human_systems"] = {k: {"items": v["items"], "m": dict(v["m"]), "a": dict(v["a"]), "e": dict(v["e"]),
                              "gemma_p_same": sum(v["p_same"]) / len(v["p_same"]) if v["p_same"] else None}
                          for k, v in hs.items()}
    pp = collections.defaultdict(lambda: collections.Counter())
    for r in pairs:
        for v in r["ratings"].values():
            if v.get("p"):
                pp[f"{r['contrast']}|{r['a']}|{r['b']}"][v["p"]] += 1
    A["human_pairs"] = {k: dict(v) for k, v in pp.items()}

    # ---- training curves
    def hist(p):
        p = S.ROOT / p
        return json.load(open(p)) if p.exists() else None
    A["training"] = {"model3": hist("step2/out/runs/arat5-v1/log_history.json"),
                     "retrain": hist("mix/out_all/runs/arat5-v1-mix/log_history.json"),
                     "retrain_selection": hist("mix/out_all/sel/choice.json"),
                     "dpo": hist("dpo2/out/runs/dpo/eval_history.json"),
                     "mrt": hist("box/v1-mrt/eval_history.json"), "mrt_gate": hist("box/v1-mrt-gate/eval_history.json"),
                     "mle": hist("box/v1-mle/eval_history.json")}

    # ---- qualitative examples (test; the shipping candidate, its net, and today's app)
    split = "test"
    items = {r["id"]: r for r in jl(d / "items" / f"{split}.jsonl")}
    P = A["per_system"][split]
    out = lambda k: {r["id"]: r["output"] for r in jl(S.outputs(split)[k])}
    ship, plain, app = out("m3-q-b4-net"), out("m3-q-b4"), out("app-arat5")
    ex = collections.defaultdict(list)
    for i, it in sorted(items.items()):
        if it["track"] == "F" or item_set(it) not in ("core", "outside"):
            continue
        r, ra = P["m3-q-b4-net"]["items"][i], P["app-arat5"]["items"][i]
        src = it["source"]
        nw = len(src.split())
        if not 8 <= nw <= 40:
            continue
        rec = {"id": i, "track": it["track"], "domain": it["domain"], "source": src, "ship": ship[i], "app": app[i],
               "ship_plain": plain[i], "p_same": r.get("p_same"), "app_p_same": ra.get("p_same"),
               "arabic": r.get("arabic"), "simpler": r.get("simpler"), "contradict": r.get("contradict"),
               "clause": r.get("clause")}
        if r.get("p_same") is None:
            continue
        if not r["copy"] and r["p_same"] >= 0.9 and (r.get("clause") or 0) >= 6 and (r.get("arabic") or 0) >= 0.9:
            ex["good"].append(rec)
        if not r["copy"] and r["p_same"] < 0.2:
            ex["slip"].append(rec)
        if not r["copy"] and r.get("arabic") is not None and r["arabic"] < 0.2 and r["p_same"] >= 0.5:
            ex["grammar"].append(rec)
        if bnorm(plain[i]) != bnorm(ship[i]):
            ex["net"].append(rec)
        if r["copy"] and not ra["copy"] and it["track"] == "C":
            ex["restraint"].append(rec)
    import random
    rng = random.Random(7)
    A["examples"] = {k: rng.sample(v, min(3, len(v))) for k, v in ex.items()}
    A["examples_counts"] = {k: len(v) for k, v in ex.items()}
    (OUT / "analysis.json").write_text(json.dumps(A, ensure_ascii=False), encoding="utf-8")
    print("analysis.json written", {k: len(v) for k, v in ex.items()})


if __name__ == "__main__":
    main()
