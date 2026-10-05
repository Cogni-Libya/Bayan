"""All figures of the report, as vector PDFs in build/fig/. Reads build/scores and build/analysis.json only."""
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

import common as C
from common import MAIN, SHIP, APP, label, color, val, diff, summ, analysis

FIG = C.BUILD / "fig"
plt.rcParams.update({"font.size": 8, "axes.titlesize": 9, "axes.labelsize": 8, "legend.fontsize": 7,
                     "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight", "pdf.fonttype": 42})
W1, W2 = 3.3, 6.9   # one column / full width (inches)
import os
SPLIT = os.environ.get("REPORT_SPLIT", "test")   # the split the single-split figures show


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)


def present(keys, split, block="meaning", name="P(same meaning)", st="core"):
    return [k for k in keys if not math.isnan(val(split, k, block, name, st)[0])]


def group_legend(ax, keys, **kw):
    gs = []
    for k in keys:
        if C.group(k) not in gs:
            gs.append(C.group(k))
    ax.legend(handles=[Patch(color=C.GROUP_COLOR[g], label=g) for g in gs], **kw)


# ---------------------------------------------------------------- 1. headline: meaning vs simplicity (Pareto)
def pareto():
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.4))
    for ax, split in zip(axs, ("dev", "test")):
        keys = present([k for k in C.S.SYSTEMS if C.group(k) != "hybrid"], split)
        pts = {}
        for k in keys:
            y = val(split, k, "meaning", "P(same meaning)")
            x = val(split, k, "simpler", "longest clause: words shorter")
            if math.isnan(x[0]):
                continue
            pts[k] = (x, y)
            big = k in (SHIP, APP)
            ax.errorbar(x[0], y[0], xerr=[[x[0] - x[1]], [x[2] - x[0]]], yerr=[[y[0] - y[1]], [y[2] - y[0]]],
                        fmt="*" if k == SHIP else "o", ms=9 if big else 4, color=color(k), ecolor=color(k),
                        elinewidth=0.5, alpha=0.95 if (big or k in MAIN) else 0.45, zorder=3 if big else 2)
        # Pareto frontier: no other system is both more faithful and simpler
        fr = sorted([k for k in pts if not any(pts[o][0][0] >= pts[k][0][0] and pts[o][1][0] >= pts[k][1][0]
                                                and o != k and (pts[o][0][0], pts[o][1][0]) != (pts[k][0][0], pts[k][1][0]) for o in pts)],
                    key=lambda k: pts[k][0][0])
        ax.plot([pts[k][0][0] for k in fr], [pts[k][1][0] for k in fr], "--", color="k", lw=0.6, zorder=1)
        offs = {APP: (-10, -11), SHIP: (-30, 9), "m3": (4, -9), "copy": (4, -6), "app-arabart": (4, -8), "m2-arabart": (4, -8)}
        for k, o in offs.items():
            if k in pts:
                ax.annotate(label(k).replace(" (ship)", "").replace("App today: ", "App "), (pts[k][0][0], pts[k][1][0]),
                            fontsize=5.5, xytext=o, textcoords="offset points", fontweight="bold" if k == SHIP else None)
        for a, b in (("m3", "m3-net"), ("m3-b4", "m3-q-b4"), ("m3-q-b4", "m3-q-b4-net")):
            if a in pts and b in pts:
                ax.annotate("", xy=(pts[b][0][0], pts[b][1][0]), xytext=(pts[a][0][0], pts[a][1][0]),
                            arrowprops=dict(arrowstyle="->", color="#555", lw=0.6))
        ax.set_xlabel("Longest clause: words shorter (core, mean, 95% CI)")
        ax.set_ylabel("P(same meaning), Gemma 4 31B")
        ax.set_title(f"BayanBench {split}, core items")
    group_legend(axs[1], [k for k in C.S.SYSTEMS if C.group(k) != "hybrid"], loc="lower left", frameon=False)
    save(fig, "pareto")


def pareto_main():
    """The main systems only, numbered, one panel per split."""
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.3))
    keys = MAIN
    for ax, split in zip(axs, ("dev", "test")):
        for i, k in enumerate(keys, 1):
            y = val(split, k, "meaning", "P(same meaning)")
            x = val(split, k, "simpler", "longest clause: words shorter")
            if math.isnan(x[0]) or math.isnan(y[0]):
                continue
            ax.errorbar(x[0], y[0], xerr=[[x[0] - x[1]], [x[2] - x[0]]], yerr=[[y[0] - y[1]], [y[2] - y[0]]],
                        fmt="*" if k == SHIP else "o", ms=10 if k == SHIP else 5, color=color(k), elinewidth=0.4, alpha=0.9)
            ax.annotate(str(i), (x[0], y[0]), fontsize=6.5, xytext=(4, 2), textcoords="offset points",
                        fontweight="bold" if k in (SHIP, APP) else None)
        ax.set_xlabel("Longest clause: words shorter"); ax.set_ylabel("P(same meaning)")
        ax.set_title(f"{split}, core items")
    fig.legend(handles=[Line2D([], [], marker="*" if k == SHIP else "o", ls="", color=color(k), label=f"{i}  {label(k)}")
                        for i, k in enumerate(keys, 1)], loc="center left", bbox_to_anchor=(1.0, 0.5), frameon=False, fontsize=6.5)
    save(fig, "pareto_main")


# ---------------------------------------------------------------- 2. meaning bars (all systems)
def meaning_bars():
    for split in ("dev", "test"):
        keys = present([k for k in C.S.SYSTEMS if C.group(k) != "hybrid"], split)
        if not keys:
            continue
        keys.sort(key=lambda k: val(split, k, "meaning", "P(same meaning)")[0])
        fig, axs = plt.subplots(1, 3, figsize=(W2, 0.17 * len(keys) + 0.8), sharey=True)
        for ax, (block, name, ttl, sc) in zip(axs, (("meaning", "P(same meaning)", "P(same meaning)", 1),
                                                    ("meaning", "meaning kept", "Meaning kept (%)", 1),
                                                    ("meaning", "meaning kept and simpler", "Kept and simpler (%)", 1))):
            v = np.array([val(split, k, block, name) for k in keys])
            y = np.arange(len(keys))
            ax.barh(y, v[:, 0], xerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], color=[color(k) for k in keys],
                    error_kw=dict(lw=0.5, capsize=1.5), height=0.7)
            ax.set_title(ttl)
            ref = val(split, APP, block, name)[0]
            if not math.isnan(ref):
                ax.axvline(ref, color=C.GROUP_COLOR["app"], ls=":", lw=0.8)
        axs[0].set_yticks(np.arange(len(keys)), [label(k) for k in keys])
        for k, t in zip(keys, axs[0].get_yticklabels()):
            if k == SHIP:
                t.set_fontweight("bold")
        fig.suptitle(f"Meaning, {split} core items (dotted line: today's app)", fontsize=9, y=1.01)
        save(fig, f"meaning_bars_{split}")


# ---------------------------------------------------------------- 3. why meaning fails: added / missing / contradict
def failure_modes():
    split = SPLIT
    keys = [k for k in MAIN if summ(split, k).get("missing")]
    fig, ax = plt.subplots(figsize=(W2, 2.6))
    x = np.arange(len(keys)); w = 0.27
    for j, (f, c) in enumerate((("added", "#8c564b"), ("missing", "#e377c2"), ("contradict", "#7f7f7f"))):
        v = np.array([summ(split, k)[f] for k in keys])
        ax.bar(x + (j - 1) * w, v[:, 0], w, yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], color=c, label=f"P({f})",
               error_kw=dict(lw=0.5))
    ax.set_xticks(x, [label(k) for k in keys], rotation=40, ha="right")
    ax.set_ylabel("Mean over core items (copies = 0)")
    ax.legend(frameon=False)
    ax.set_title("Why meaning is lost (test, core): Gemma 31B's three failure questions")
    save(fig, "failure_modes")


def contradiction():
    split = SPLIT
    keys = [k for k in MAIN if summ(split, k).get("contradict_rate_changed")]
    fig, ax = plt.subplots(figsize=(W1, 2.6))
    v = np.array([summ(split, k)["contradict_rate_changed"] for k in keys])
    y = np.arange(len(keys))
    ax.barh(y, v[:, 0], xerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], color=[color(k) for k in keys], error_kw=dict(lw=0.5))
    ax.set_yticks(y, [label(k) for k in keys])
    ax.set_xlabel("% of changed outputs with P(contradict) ≥ 0.5")
    ax.set_title("Contradictions among changed outputs (test, core)")
    save(fig, "contradiction")


# ---------------------------------------------------------------- 4. per-item distribution of P(same)
def violins():
    split = SPLIT
    keys = [k for k in ["app-arat5", "app-arabart", "m2-arat5-nt", "m2-arabart", "m3", "m3-net", "m3-q-b4-net", "rt-q-b4-net"]]
    A = analysis()["per_system"][split]
    data, labs = [], []
    for k in keys:
        xs = [r["p_same"] for r in A[k]["items"].values() if r["set"] == "core" and "p_same" in r and not r["copy"]]
        if xs:
            data.append(xs); labs.append(f"{label(k)}\n(n={len(xs)})")
    fig, ax = plt.subplots(figsize=(W2, 2.6))
    parts = ax.violinplot(data, showmedians=True, widths=0.8)
    for b, k in zip(parts["bodies"], keys):
        b.set_facecolor(color(k)); b.set_alpha(0.6)
    ax.set_xticks(np.arange(1, len(data) + 1), labs, fontsize=5.5, rotation=25, ha="right")
    ax.set_ylabel("P(same meaning)")
    ax.set_title("Per-item P(same) on changed outputs only (test, core): copies excluded, so copying cannot inflate it")
    save(fig, "violins")


# ---------------------------------------------------------------- 5. simplicity
def simplicity():
    split = SPLIT
    keys = present(MAIN, split)
    fig, axs = plt.subplots(1, 3, figsize=(W2, 3.0), sharey=True)
    for ax, (name, ttl) in zip(axs, (("longest clause: words shorter", "Clause: words shorter"),
                                     ("reading level: levels lower", "Reading level: levels lower"),
                                     ("hard words: fewer", "Hard words (SAMER L4-5): fewer"))):
        v = np.array([val(split, k, "simpler", name) for k in keys])
        y = np.arange(len(keys))
        ax.barh(y, v[:, 0], xerr=[np.nan_to_num(v[:, 0] - v[:, 1]), np.nan_to_num(v[:, 2] - v[:, 0])],
                color=[color(k) for k in keys], error_kw=dict(lw=0.5))
        ax.axvline(0, color="k", lw=0.5)
        ax.set_title(ttl)
    axs[0].set_yticks(np.arange(len(keys)), [label(k) for k in keys])
    fig.suptitle("How much simpler (test, core; mean change on the items that have something to simplify, 95% CI)", fontsize=9, y=1.03)
    save(fig, "simplicity")


# ---------------------------------------------------------------- 6. safety and restraint
def safety():
    split = SPLIT
    keys = present(MAIN, split)
    ms = [("checks", "numbers kept", "Numbers kept"), ("behaviour", "C: easy text left unchanged", "Easy text unchanged"),
          ("behaviour", "F: letters unchanged", "Protected text: letters kept"), ("behaviour", "E1: end mark kept", "Cut-off ending kept")]
    fig, axs = plt.subplots(1, 4, figsize=(W2, 3.0), sharey=True)
    for ax, (b, n, t) in zip(axs, ms):
        v = np.array([val(split, k, b, n) for k in keys])
        y = np.arange(len(keys))
        ax.barh(y, v[:, 0], xerr=[np.nan_to_num(v[:, 0] - v[:, 1]), np.nan_to_num(v[:, 2] - v[:, 0])],
                color=[color(k) for k in keys], error_kw=dict(lw=0.5))
        ax.set_xlim(0, 105); ax.set_title(t, fontsize=7.5)
    axs[0].set_yticks(np.arange(len(keys)), [label(k) for k in keys])
    fig.suptitle("Safety and restraint (test, core, %)", fontsize=9, y=1.03)
    save(fig, "safety")


def flags_heatmap():
    split = SPLIT
    keys = present(MAIN, split)
    ms = [("flags", "negation changed"), ("flags", "limit changed"), ("flags", "condition changed"),
          ("diagnostics", "mid-sentence full stop added"), ("checks", "no house-rule break")]
    M = np.array([[val(split, k, b, n)[0] for b, n in ms] for k in keys])
    fig, ax = plt.subplots(figsize=(W1 + 0.6, 3.2))
    disp = M.copy(); disp[:, -1] = 100 - disp[:, -1]
    im = ax.imshow(disp, cmap="Reds", vmin=0, vmax=max(40, np.nanmax(disp)), aspect="auto")
    for i in range(len(keys)):
        for j in range(len(ms)):
            if not math.isnan(disp[i, j]):
                ax.text(j, i, f"{disp[i, j]:.0f}", ha="center", va="center", fontsize=6,
                        color="white" if disp[i, j] > 25 else "black")
    ax.set_xticks(range(len(ms)), ["negation\nchanged", "limit\nchanged", "condition\nchanged", "full stop\nadded", "house-rule\nbreak"], fontsize=6)
    ax.set_yticks(range(len(keys)), [label(k) for k in keys])
    ax.set_title("Risk flags (test, core, % of items; lower is safer)")
    fig.colorbar(im, ax=ax, shrink=0.6)
    save(fig, "flags_heatmap")


# ---------------------------------------------------------------- 7. one-glance heatmap of every measure
def scoreboard():
    for split in ("dev", "test"):
        keys = present([k for k in C.S.SYSTEMS if C.group(k) != "hybrid"], split)
        if not keys:
            continue
        ms = [m for m in C.MEASURES]
        M = np.array([[val(split, k, b, n)[0] for b, n, _, _ in ms] for k in keys])
        Z = np.full_like(M, np.nan)
        for j, (b, n, _, _) in enumerate(ms):
            col = M[:, j]
            if np.all(np.isnan(col)) or np.nanmax(col) == np.nanmin(col):
                continue
            z = (col - np.nanmin(col)) / (np.nanmax(col) - np.nanmin(col))
            Z[:, j] = 1 - z if n in C.LOWER_BETTER else z
        fig, ax = plt.subplots(figsize=(W2, 0.19 * len(keys) + 1.3))
        ax.imshow(Z, cmap="RdYlGn", vmin=-0.6, vmax=1.6, aspect="auto")   # muted, so the numbers stay readable
        for i in range(len(keys)):
            for j in range(len(ms)):
                if not math.isnan(M[i, j]):
                    ax.text(j, i, f"{M[i, j]:.2f}" if ms[j][3] == "mean" else f"{M[i, j]:.0f}", ha="center", va="center", fontsize=5)
        ax.set_xticks(range(len(ms)), [m[2] for m in ms], rotation=50, ha="right", fontsize=6)
        ax.set_yticks(range(len(keys)), [label(k) for k in keys], fontsize=6)
        ax.set_title(f"Every measure, every system ({split}, core). Colour: rank within the column (green = better)")
        save(fig, f"scoreboard_{split}")


# ---------------------------------------------------------------- 8. Arabic quality (diagnostic)
def arabic():
    split = SPLIT
    keys = [k for k in MAIN if summ(split, k).get("arabic")]
    fig, axs = plt.subplots(1, 3, figsize=(W2, 3.0), sharey=True)
    for ax, (f, t) in zip(axs, (("arabic", "Arabic correct"), ("coherent", "Coherent"), ("simpler", "Easier to read"))):
        v = np.array([summ(split, k)[f] for k in keys])
        y = np.arange(len(keys))
        ax.barh(y, v[:, 0], xerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], color=[color(k) for k in keys], error_kw=dict(lw=0.5))
        ax.set_xlim(0, 1); ax.set_title(t)
    axs[0].set_yticks(np.arange(len(keys)), [label(k) for k in keys])
    fig.suptitle("Gemma 31B extra questions (test, core; mean P(yes); diagnostic: weak agreement with raters)", fontsize=9, y=1.03)
    save(fig, "arabic")


# ---------------------------------------------------------------- 9. the judge vs humans
def _cm(ax, d, rows, cols, title):
    M = np.array([[d.get(f"{r}|{c}", 0) for c in cols] for r in rows])
    ax.imshow(M / np.maximum(M.sum(1, keepdims=True), 1), cmap="Blues", vmin=0, vmax=1, aspect="auto")
    for i in range(len(rows)):
        for j in range(len(cols)):
            tot = M[i].sum()
            ax.text(j, i, f"{M[i, j]}\n({100 * M[i, j] / tot:.0f}%)" if tot else "0", ha="center", va="center", fontsize=6.5,
                    color="white" if tot and M[i, j] / tot > 0.6 else "black")
    ax.set_xticks(range(len(cols)), cols); ax.set_yticks(range(len(rows)), rows)
    ax.set_title(title, fontsize=7.5)


def judge_validation():
    hv = analysis()["human_validation"]
    fig, axs = plt.subplots(1, 4, figsize=(W2, 2.1), gridspec_kw={"wspace": 0.75})
    _cm(axs[0], hv["confusion_meaning"], ["same", "minor", "major", "tie"], ["kept", "not kept"], "Gemma 31B (P(same) ≥ 0.5)\nvs human majority")
    if "confusion_mimo" in hv:
        _cm(axs[1], hv["confusion_mimo"], ["same", "minor", "major"], ["kept", "not kept"], "MiMo (second judge pilot)\nvs human majority")
    _cm(axs[2], hv["confusion_arabic"], ["ok", "minor", "major", "tie"], ["yes", "no"], "Gemma 'Arabic correct'\nvs human Arabic")
    _cm(axs[3], hv["confusion_ease"], ["easier", "same", "harder", "tie"], ["yes", "no"], "Gemma 'easier'\nvs human ease")
    axs[0].set_ylabel("human majority")
    save(fig, "confusion")

    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.3), gridspec_kw={"wspace": 0.45})
    r = np.array(hv["roc_same"])
    axs[0].plot(r[:, 0], r[:, 1], color=C.GROUP_COLOR["model 3 family"], label=f"Gemma 31B, AUC {hv['auc_same']:.2f}")
    if "roc_mimo" in hv:
        r = np.array(hv["roc_mimo"])
        axs[0].plot(r[:, 0], r[:, 1], color="#ff7f0e", label=f"MiMo, AUC {hv['auc_mimo']:.2f}")
    axs[0].plot([0, 1], [0, 1], ":", color="grey", lw=0.6)
    axs[0].set_xlabel("False 'kept' rate (humans: changed)"); axs[0].set_ylabel("True 'kept' rate (humans: same)")
    axs[0].legend(frameon=False, loc="lower right"); axs[0].set_title("ROC: meaning kept vs human majority 'same'")
    sw = hv["sweep"]
    t = [s["t"] for s in sw]
    for f, lab, c in (("acc", "accuracy", "k"), ("bal", "balanced accuracy", "#1f77b4"), ("tpr", "same kept", "#2ca02c"), ("tnr", "changes caught", "#d62728")):
        axs[1].plot(t, [s[f] for s in sw], label=lab, color=c, lw=1)
    best = max(sw, key=lambda s: s["bal"])
    axs[1].axvline(0.5, ls="--", color="grey", lw=0.6); axs[1].axvline(best["t"], ls=":", color="#1f77b4", lw=0.6)
    axs[1].text(0.51, 0.04, "frozen 0.5", fontsize=6, transform=axs[1].get_xaxis_transform())
    axs[1].text(best["t"] + 0.01, 0.12, f"best balanced {best['t']:.2f}", fontsize=6, color="#1f77b4", transform=axs[1].get_xaxis_transform())
    axs[1].set_xlabel("P(same) threshold"); axs[1].legend(frameon=False, fontsize=5.5); axs[1].set_title("Threshold sweep")
    cb = hv["calibration"]
    axs[2].plot([0, 1], [0, 1], ":", color="grey", lw=0.6)
    axs[2].plot([b["mean_p"] for b in cb], [b["human_same"] for b in cb], "o-", ms=3)
    for b in cb:
        axs[2].annotate(str(b["n"]), (b["mean_p"], b["human_same"]), fontsize=5, xytext=(2, -7), textcoords="offset points")
    axs[2].set_xlabel("Gemma P(same), bin mean"); axs[2].set_ylabel("share humans say 'same'")
    axs[2].set_title("Calibration (n per bin)")
    save(fig, "judge_roc")

    raters = hv["raters"]
    K = np.full((len(raters), len(raters)), np.nan)
    for k, v in hv["pair_kappa"].items():
        a, b = k.split("|"); i, j = raters.index(a), raters.index(b)
        K[i, j] = K[j, i] = v["kappa"]
    fig, axs = plt.subplots(1, 2, figsize=(W2, 2.3), gridspec_kw={"width_ratios": [1.2, 1]})
    im = axs[0].imshow(K, cmap="viridis", vmin=-0.2, vmax=1)
    names = [f"rater {i + 1}" for i in range(len(raters))]
    for i in range(len(raters)):
        for j in range(len(raters)):
            if not math.isnan(K[i, j]):
                axs[0].text(j, i, f"{K[i, j]:.2f}", ha="center", va="center", fontsize=6, color="white" if K[i, j] < 0.5 else "black")
    axs[0].set_xticks(range(len(raters)), names, rotation=30); axs[0].set_yticks(range(len(raters)), names)
    axs[0].set_title("Rater pairs: Cohen's κ on 'same meaning' (≥15 shared items)")
    fig.colorbar(im, ax=axs[0], shrink=0.7)
    rv = hv["rater_vs_scorer"]
    ks = [r for r in raters if r in rv]
    axs[1].bar(range(len(ks)), [rv[r]["kappa"] for r in ks], color="#1f77b4")
    for i, r in enumerate(ks):
        axs[1].text(i, rv[r]["kappa"] + 0.02, f"n={rv[r]['n']}", ha="center", fontsize=5.5)
    axs[1].set_xticks(range(len(ks)), [names[raters.index(r)] for r in ks], rotation=30)
    axs[1].set_ylabel("Cohen's κ"); axs[1].set_title("Each rater vs Gemma (kept at 0.5)")
    save(fig, "raters")


# ---------------------------------------------------------------- 10. human ratings per system and pairwise preferences
def human():
    hs = analysis()["human_systems"]
    order = ["app-arat5", "app-arabart", "model2-arat5", "model2-arat5-notag", "model2-arabart", "model2-arabart-notag"]
    names = {"app-arat5": "App AraT5", "app-arabart": "App AraBART", "model2-arat5": "M2 AraT5 [S2]",
             "model2-arat5-notag": "M2 AraT5 no tag", "model2-arabart": "M2 AraBART [S2]", "model2-arabart-notag": "M2 AraBART no tag"}
    order = [k for k in order if k in hs]
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.2), sharey=True)
    for ax, (axis, cats, cols, t) in zip(axs, (("m", ["same", "minor", "major"], ["#2ca02c", "#ffbf00", "#d62728"], "Meaning"),
                                               ("a", ["ok", "minor", "major"], ["#2ca02c", "#ffbf00", "#d62728"], "Arabic"),
                                               ("e", ["easier", "same", "harder"], ["#2ca02c", "#bbbbbb", "#d62728"], "Ease"))):
        left = np.zeros(len(order))
        for c, col in zip(cats, cols):
            v = np.array([hs[k][axis].get(c, 0) / max(sum(hs[k][axis].values()), 1) * 100 for k in order])
            ax.barh(range(len(order)), v, left=left, color=col, label=c)
            left += v
        ax.set_title(t); ax.legend(frameon=False, fontsize=5.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    axs[0].set_yticks(range(len(order)), [f"{names[k]} (n={hs[k]['items']})" for k in order])
    fig.suptitle("Human ratings, BayanBench v2 round (3 Oct; % of individual ratings)", fontsize=9, y=1.05)
    save(fig, "human_systems")

    hp = {}
    for k, d in analysis()["human_pairs"].items():   # one orientation per pair of systems
        c, x, y = k.split("|")
        if x > y:
            x, y, d = y, x, {"a": d.get("b", 0), "b": d.get("a", 0), "same": d.get("same", 0)}
        t = hp.setdefault(f"{c}|{x}|{y}", {"a": 0, "b": 0, "same": 0})
        for kk in t:
            t[kk] += d.get(kk, 0)
    fig, ax = plt.subplots(figsize=(W1 + 0.8, 0.16 * len(hp) + 0.8))
    rows = sorted(hp)
    for i, k in enumerate(rows):
        c, a, b = k.split("|")
        d = hp[k]; tot = sum(d.values())
        left = 0
        for kk, col in (("a", "#1f77b4"), ("same", "#bbbbbb"), ("b", "#ff7f0e")):
            w = 100 * d.get(kk, 0) / tot
            ax.barh(i, w, left=left, color=col); left += w
    ax.set_yticks(range(len(rows)), [f"{k.split('|')[0]}: {names.get(k.split('|')[1], k.split('|')[1])} vs {names.get(k.split('|')[2], k.split('|')[2])} (n={sum(hp[k].values())})" for k in rows], fontsize=6)
    ax.legend(handles=[Patch(color="#1f77b4", label="prefer first"), Patch(color="#bbbbbb", label="no preference"),
                       Patch(color="#ff7f0e", label="prefer second")], frameon=False, fontsize=5.5, ncol=3, loc="upper center", bbox_to_anchor=(0.4, -0.15))
    ax.set_xlabel("% of ratings"); ax.set_title("Pairwise preferences")
    save(fig, "human_pairs")


# ---------------------------------------------------------------- 11. the int8 / decoding / net factorial
def factorial():
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.6))
    split = SPLIT
    combos = [("greedy", "", "-b4"), ]
    for ax, (name, block, ttl) in zip(axs, (("P(same meaning)", "meaning", "P(same)"),
                                             ("longest clause: words shorter", "simpler", "Clause: words shorter"),
                                             ("reading level: levels lower", "simpler", "Levels lower"))):
        rows = [("Model 3", "m3", "m3-q", "#1f77b4"), ("Retrain", "rt", "rt-q", "#9467bd")]
        xt = ["greedy", "greedy\n+net", "beam 4", "beam 4\n+net"]
        for lab, fl, q, c in rows:
            for prec, base, ls in (("float", fl, "-"), ("app int8", q, "--")):
                ks = [base, base + "-net", base + "-b4", base + "-b4-net"]
                v = np.array([val(split, k, block, name) for k in ks])
                ax.errorbar(np.arange(4) + (0.05 if prec == "app int8" else -0.05), v[:, 0], yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]],
                            fmt="o" + ls, color=c, ms=3, lw=0.9, elinewidth=0.5, label=f"{lab}, {prec}")
        ref = val(split, APP, block, name)[0]
        ax.axhline(ref, color=C.GROUP_COLOR["app"], ls=":", lw=0.8)
        ax.set_xticks(range(4), xt); ax.set_title(ttl)
    axs[0].legend(frameon=False, fontsize=5.5, loc="upper center", bbox_to_anchor=(1.8, -0.25), ncol=4)
    fig.suptitle("Precision × decoding × safety net (test, core; dotted: today's app)", fontsize=9, y=1.03)
    fig.subplots_adjust(wspace=0.35)
    save(fig, "factorial")


def hybrid():
    fig, axs = plt.subplots(1, 2, figsize=(W2 * 0.7, 2.2))
    for ax, (block, name, t) in zip(axs, (("meaning", "P(same meaning)", "P(same)"), ("simpler", "longest clause: words shorter", "Clause: words shorter"))):
        for split, c in (("dev", "#1f77b4"), ("test", "#ff7f0e")):
            xs = [0, 10, 20, 30, 50, 100]
            v = np.array([val(split, f"hyb{p}", block, name) for p in xs])
            ax.errorbar(xs, v[:, 0], yerr=[v[:, 0] - v[:, 1], v[:, 2] - v[:, 0]], fmt="o-", ms=3, color=c, label=split, elinewidth=0.5)
        ax.set_xlabel("% of sentences on beam 4"); ax.set_title(t)
    axs[0].legend(frameon=False)
    save(fig, "hybrid")


# ---------------------------------------------------------------- 12. item sets: ship vs app
def sets():
    split = SPLIT
    ms = [("meaning", "P(same meaning)", "P(same)"), ("simpler", "longest clause: words shorter", "Clause shorter"),
          ("simpler", "reading level: levels lower", "Levels lower"), ("checks", "numbers kept", "Numbers kept (%)")]
    fig, axs = plt.subplots(1, 4, figsize=(W2, 2.0))
    keys = [APP, "m2-arat5-nt", "m3-net", SHIP]
    for ax, (b, n, t) in zip(axs, ms):
        for j, k in enumerate(keys):
            v = np.array([val(split, k, b, n, st) for st in C.SETS])
            ax.errorbar(np.arange(4) + (j - 1.5) * 0.12, v[:, 0], yerr=[np.nan_to_num(v[:, 0] - v[:, 1]), np.nan_to_num(v[:, 2] - v[:, 0])],
                        fmt="o", ms=3, color=color(k) if k != "m3-net" else "#6baed6", elinewidth=0.5, label=label(k))
        ax.set_xticks(range(4), C.SETS, rotation=30); ax.set_title(t)
    fig.subplots_adjust(wspace=0.4)
    axs[0].legend(frameon=False, fontsize=5.5, loc="upper center", bbox_to_anchor=(2.4, -0.35), ncol=4)
    fig.suptitle("By item set (test): BAREC core, held-out news/legal, outside texts, written leaflets", fontsize=9, y=1.05)
    save(fig, "sets")


# ---------------------------------------------------------------- 13. ship gate: paired differences vs today's app
def gate():
    fig, axs = plt.subplots(1, 2, figsize=(W2, 3.0))
    ms = [m for m in C.MEASURES if m[1] not in ("F: letters unchanged",)]
    for ax, split in zip(axs, ("dev", "test")):
        rows = []
        for b, n, lab, kind in ms:
            d = diff(split, SHIP, b, n)
            if math.isnan(d[0]):
                continue
            sgn = -1 if n in C.LOWER_BETTER else 1
            rows.append((lab + (" (pts)" if kind == "rate" else ""), d, sgn, kind))
        y = np.arange(len(rows))[::-1]
        for yy, (lab, d, sgn, kind) in zip(y, rows):
            better = (sgn * d[1] > 0) if sgn > 0 else (sgn * d[2] > 0)
            worse = (sgn * d[2] < 0) if sgn > 0 else (sgn * d[1] < 0)
            c = "#2ca02c" if better else ("#d62728" if worse else "#7f7f7f")
            sc = 100 if kind == "mean" and "P(same" in lab else 1
            ax.errorbar(d[0] * sc, yy, xerr=[[(d[0] - d[1]) * sc], [(d[2] - d[0]) * sc]], fmt="o", color=c, ms=3, elinewidth=0.8)
        ax.axvline(0, color="k", lw=0.5)
        ax.set_yticks(y, [r[0].replace("P(same)", "P(same) ×100") for r in rows], fontsize=6)
        ax.set_title(f"{split}: ship candidate − today's app\n(paired, 95% CI)", fontsize=8)
    axs[1].legend(handles=[Line2D([], [], marker="o", ls="", color="#2ca02c", label="better"), Line2D([], [], marker="o", ls="", color="#d62728", label="worse"),
                           Line2D([], [], marker="o", ls="", color="#7f7f7f", label="not significant")], frameon=False, fontsize=6, loc="lower right")
    save(fig, "gate")


# ---------------------------------------------------------------- 14. training
def training():
    T = analysis()["training"]
    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.2), gridspec_kw={"wspace": 0.35})
    for key, c, lab in (("model3", "#1f77b4", "Model 3"), ("retrain", "#9467bd", "Fluency retrain")):
        h = [r for r in (T.get(key) or []) if "eval_sari_changed" in r]
        if not h:
            continue
        s = [r["step"] for r in h]
        axs[0].plot(s, [r["eval_sari_changed"] for r in h], "o-", ms=2, color=c, label=lab)
        axs[1].plot(s, [r["eval_copy_rate"] for r in h], "o-", ms=2, color=c, label=lab)
        axs[2].plot(s, [r["eval_edit_rate_unchanged"] for r in h], "o-", ms=2, color=c, label=lab)
    axs[0].set_title("SARI on changed dev rows"); axs[1].set_title("Copies the input (%)"); axs[2].set_title("Edits rows that should stay (%)")
    for ax in axs:
        ax.set_xlabel("step")
    axs[0].legend(frameon=False)
    save(fig, "training_curves")

    fig, axs = plt.subplots(1, 3, figsize=(W2, 2.4), gridspec_kw={"wspace": 0.75})
    sel = (T.get("retrain_selection") or {}).get("table", {})
    ks = [k for k in sel if k != "reference"]
    if ks:
        st = [int(k.split("-")[1]) for k in ks]
        axs[0].plot(st, [sel[k]["arabic"] for k in ks], "o-", ms=3, label="Gemma Arabic")
        axs[0].plot(st, [sel[k]["p_same"] for k in ks], "s-", ms=3, label="P(same)")
        axs[0].axhline(sel["reference"]["arabic"], ls=":", color="C0", lw=0.7); axs[0].axhline(sel["reference"]["p_same"], ls=":", color="C1", lw=0.7)
        ax2 = axs[0].twinx(); ax2.plot(st, [sel[k]["sari"] for k in ks], "^--", ms=3, color="grey", label="SARI"); ax2.set_ylabel("SARI", fontsize=6)
        axs[0].legend(frameon=False, fontsize=5.5); axs[0].set_title("Retrain checkpoints\n(dotted: model 3)", fontsize=7.5); axs[0].set_xlabel("step")
    d = T.get("dpo") or []
    if d:
        s = [r["step"] for r in d]
        axs[1].plot(s, [r["sari_changed"] for r in d], "o-", ms=3, label="SARI changed")
        ax2 = axs[1].twinx()
        ax2.plot(s, [100 * r["keep_unchanged"] for r in d], "s--", ms=3, color="C2", label="keeps unchanged %")
        ax2.plot(s, [100 * r["numbers_kept"] for r in d], "^--", ms=3, color="C3", label="numbers kept %")
        axs[1].set_title("Student DPO:\nproxies improved", fontsize=7.5); axs[1].set_xlabel("step"); ax2.legend(frameon=False, fontsize=5.5, loc="lower right")
    m = T.get("mrt") or []
    if m:
        s = [r["step"] for r in m]
        axs[2].plot(s, [r["judge_same_mean"] for r in m], "o-", ms=3, label="judge P(same)")
        axs[2].plot(s, [r["copy_generated"] for r in m], "s-", ms=3, label="copy rate")
        axs[2].plot(s, [r["lead_ge2"] for r in m], "^-", ms=3, label="readability lead ≥ 2")
        axs[2].set_title("MRT (AraBART,\njudge in the loss)", fontsize=7.5); axs[2].set_xlabel("step"); axs[2].legend(frameon=False, fontsize=5.5)
    save(fig, "training_other")


# ---------------------------------------------------------------- 15. on-device cost
def device():
    import json
    f = C.HERE / "facts.json"
    if not f.exists():
        return
    F = json.load(open(f))["device"]
    fig, ax = plt.subplots(figsize=(W1, 2.4))
    for r in F:
        ax.scatter(r["size_mb"], r["s_per_sentence"], color=r.get("color", "#1f77b4"), s=20, marker="*" if r.get("ship") else "o")
        ax.annotate(r["name"], (r["size_mb"], r["s_per_sentence"]), fontsize=5.5, xytext=(3, 2), textcoords="offset points")
    ax.set_xlabel("Download size (MB)"); ax.set_ylabel("CPU seconds per sentence (4 threads)")
    ax.set_title("Size vs speed (laptop CPUs; see Table for hardware)")
    save(fig, "device")


if __name__ == "__main__":
    for f in (pareto, pareto_main, meaning_bars, failure_modes, contradiction, violins, simplicity, safety, flags_heatmap, scoreboard,
              arabic, judge_validation, human, factorial, hybrid, sets, gate, training, device):
        try:
            f()
            print("ok", f.__name__)
        except Exception as e:  # keep going; the report marks missing figures
            import traceback; traceback.print_exc()
            print("FAILED", f.__name__, e)
