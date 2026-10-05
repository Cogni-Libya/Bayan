"""Write bench_v2.tex: model 2 on BayanBench v2, from the scorecards in eval/bench_v2/ (eval/bench_v2/run.sh writes them
with the bench's own CLI, `bayanbench score --json`).

    python make_bench_v2.py

Meaning kept = P(same) >= 0.5 and every number kept (threshold frozen from the human ratings). Item sets are reported
side by side, never averaged. A meaning cell whose scores are incomplete (under 90% of items scored) prints "pending";
the macros \\benchheadsplit and \\benchmeaningcomplete say which split is the headline."""
import json
from pathlib import Path

E = Path("eval/bench_v2")
SYSTEMS = {
    "copy": "Copy the input",
    "model2-arat5": r"v0.2, \texttt{[S2]}",
    "model2-arabart": r"v0.2-Fast, \texttt{[S2]}",
    "model2-arat5-notag": "v0.2, no tag",
    "model2-arabart-notag": "v0.2-Fast, no tag",
    "app-arat5": "v0.2, int8 app",
    "app-arabart": "v0.2-Fast, int8 app",
}
STYLE = {"copy": "pcopy", "model2-arat5": "ptfives", "model2-arabart": "pbarts", "model2-arat5-notag": "ptfiven",
         "model2-arabart-notag": "pbartn", "app-arat5": "ptfivea", "app-arabart": "pbarta"}
COLS = ["copy", "model2-arat5", "model2-arabart", "app-arat5", "app-arabart"]
SETS = ["core", "held-out", "outside", "written"]
ROWS = [  # block, measure, label, kind (rate / mean), higher is better?
    ("Meaning", "meaning", "meaning kept", r"Meaning kept (P(same) $\geq$ 0.5, numbers kept), \%", "rate", True),
    ("Meaning", "meaning", "P(same meaning)", "Mean P(same meaning)", "mean2", True),
    ("Simpler (mean change)", "simpler", "longest clause: words shorter", "Longest clause: words cut (clause over 15)", "mean1", True),
    ("Simpler (mean change)", "simpler", "reading level: levels lower", "Reading level: levels lower (level 10+)", "mean2", True),
    ("Simpler (mean change)", "simpler", "hard words: fewer", "Hard words removed (items with any)", "mean2", True),
    ("Checks, \\%", "checks", "numbers kept", "Every number kept", "rate", True),
    ("Checks, \\%", "checks", "no house-rule break", "No house-rule break", "rate", True),
    ("Behaviour, \\%", "behaviour", "C: easy text left unchanged", "Easy text left unchanged (C)", "rate", True),
    ("Behaviour, \\%", "behaviour", "E1: end mark kept", "Cut-off selection keeps its ending (E1)", "rate", True),
    ("Behaviour, \\%", "behaviour", "F: letters unchanged", "Protected text: letters unchanged (F)", "rate", True),
    ("Flags (not failures), \\%", "flags", "negation changed", "Negation count changed", "rate", None),
]


def load(split, name):
    p = E / f"{split}.{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def entry(res, s, block, measure):
    return (res or {}).get("sets", {}).get(s, {}).get(block, {}).get(measure)


def value(e, kind):
    return e["mean" if kind.startswith("mean") else "rate"]


def fmtv(m, kind, measure):
    if kind == "rate":
        return f"{m:.1f}"
    dec = int(kind[-1])
    return f"{m:.{dec}f}" if measure == "P(same meaning)" else f"{m:+.{dec}f}"


def cell2(e, kind, measure, bold=False):
    if e is None:
        return "---"
    if e.get("complete") is False:
        return r"{\scriptsize pending}"
    m, lo, hi = value(e, kind)
    if m != m:
        return "---"
    v = fmtv(m, kind, measure)
    v = r"\textbf{" + v + "}" if bold else v
    if abs(lo - hi) < 1e-9:
        return v
    r = f"{lo:.0f}--{hi:.0f}" if kind == "rate" else f"{fmtv(lo, kind, measure)}, {fmtv(hi, kind, measure)}"
    return r"\makecell{" + v + r"\\[-2pt]{\tiny[" + r + "]}}"


def table(split, s, label, caption, cols=COLS):
    res = {c: load(split, c) for c in cols}
    out = [r"\begin{table}[h]", r"\small", r"\caption{" + caption + "}", r"\label{" + label + "}",
           r"\begin{tabularx}{\linewidth}{|L|" + "C{15.4mm}|" * len(cols) + "C{7mm}|}", r"\hline",
           r"\head{Measure} & " + " & ".join(r"\head{" + SYSTEMS[c] + "}" for c in cols) + r" & \head{$n$} \\ \hline"]
    group, omitted = None, False
    for g, block, measure, lab, kind, up in ROWS:
        es = [entry(res[c], s, block, measure) for c in cols]
        if all(e is None for e in es):
            continue
        if all(e is None or e.get("complete") is False for c, e in zip(cols, es) if c != "copy"):
            omitted = True                     # not scored yet on this split: leave the row out, say so in the caption
            continue
        if g != group:
            out.append(r"\multicolumn{" + str(len(cols) + 2) + r"}{|l|}{\cellcolor{sichead}\textbf{" + g + r"}} \\ \hline")
            group = g
        vals = [(c, value(e, kind)[0]) for c, e in zip(cols, es)
                if c != "copy" and e is not None and e.get("complete") is not False and value(e, kind)[0] == value(e, kind)[0]]
        best = (max if up else min)(v for _, v in vals) if vals and up is not None else None
        cells = [cell2(e, kind, measure, bold=(best is not None and c != "copy" and e is not None
                                               and e.get("complete") is not False and abs(value(e, kind)[0] - best) < 1e-9))
                 for c, e in zip(cols, es)]
        n = next((e["n"] for e in es if e is not None), 0)
        out.append(lab + " & " + " & ".join(cells) + f" & {n:,}" + r" \\ \hline")
    out += [r"\end{tabularx}", r"\end{table}"]
    if omitted:
        out[2] = out[2][:-1] + r" The meaning rows are left out: this split's outputs are not yet scored for meaning.}"
    return "\n".join(out)


def sets_table(split, label, caption, systems=("model2-arat5", "model2-arabart", "app-arat5", "app-arabart")):
    out = [r"\begin{table}[h]", r"\small", r"\caption{" + caption + "}", r"\label{" + label + "}",
           r"\begin{tabularx}{\linewidth}{|L|C{19mm}|C{19mm}|C{19mm}|C{19mm}|}", r"\hline",
           r"\head{System and measure} & \head{Core} & \head{Held-out} & \head{Outside} & \head{Written} \\ \hline"]
    for c in systems:
        res = load(split, c)
        out.append(r"\multicolumn{5}{|l|}{\cellcolor{sichead}\textbf{" + SYSTEMS[c] + r"}} \\ \hline")
        for block, measure, lab, kind in (("meaning", "meaning kept", r"Meaning kept, \%", "rate"),
                                          ("simpler", "longest clause: words shorter", "Longest clause: words cut", "mean1"),
                                          ("behaviour", "C: easy text left unchanged", r"Easy text left unchanged, \%", "rate")):
            cells = []
            for s in SETS:
                e = entry(res, s, block, measure)
                if e is None:
                    cells.append("---")
                elif e.get("complete") is False:
                    cells.append(r"{\scriptsize pending}")
                else:
                    cells.append(fmtv(value(e, kind)[0], kind, measure) + r"\,{\tiny(" + f"{e['n']}" + ")}")
            out.append(lab + " & " + " & ".join(cells) + r" \\ \hline")
    out += [r"\end{tabularx}", r"\end{table}"]
    return "\n".join(out)


EFFECTS = [  # baseline a, changed b, label
    ("model2-arat5", "model2-arat5-notag", r"AraT5v2: drop the \texttt{[S2]} tag"),
    ("model2-arabart", "model2-arabart-notag", r"AraBART: drop the \texttt{[S2]} tag"),
    ("model2-arat5-notag", "app-arat5", r"AraT5v2: PyTorch $\rightarrow$ int8 app"),
    ("model2-arabart-notag", "app-arabart", r"AraBART: PyTorch $\rightarrow$ int8 app"),
    ("model2-arabart", "model2-arat5", r"\texttt{[S2]}: AraBART $\rightarrow$ AraT5v2"),
    ("model2-arabart-notag", "model2-arat5-notag", r"No tag: AraBART $\rightarrow$ AraT5v2"),
    ("app-arabart", "app-arat5", r"int8 app: AraBART $\rightarrow$ AraT5v2"),
]
FX = [("meaning", "meaning kept", r"Meaning kept (points)", "rate"),
      ("simpler", "longest clause: words shorter", "Words cut from the longest clause", "mean1"),
      ("behaviour", "C: easy text left unchanged", "Easy text unchanged (points)", "rate")]


def effects_table(split, s, label, caption):
    out = [r"\begin{table}[h]", r"\small", r"\caption{" + caption + "}", r"\label{" + label + "}",
           r"\begin{tabularx}{\linewidth}{|L|C{27mm}|C{27mm}|C{27mm}|}", r"\hline",
           r"\head{One change} & " + " & ".join(r"\head{" + x[2] + "}" for x in FX) + r" \\ \hline"]
    for a, b, lab in EFFECTS:
        res = load(split, f"{b}-vs-{a}")
        cells = []
        for block, measure, _, kind in FX:
            e = entry(res, s, block, measure)
            if e is None or "diff" not in e or e.get("complete") is False:
                cells.append(r"{\scriptsize pending}" if e is not None and e.get("complete") is False else "---")
                continue
            d, lo, hi = e["diff"]
            star = r"$^{*}$" if lo > 0 or hi < 0 else ""
            dec = 1
            cells.append(f"{d:+.{dec}f}{star}" + r"\,{\tiny[" + f"{lo:+.{dec}f}, {hi:+.{dec}f}" + "]}")
        out.append(lab + " & " + " & ".join(cells) + r" \\ \hline")
    out += [r"\end{tabularx}", r"\end{table}"]
    return "\n".join(out)


def complete(split):
    for c in COLS:
        e = entry(load(split, c), "core", "meaning", "meaning kept")
        if e is None or e.get("complete") is False:
            return False
    return True


def macros():
    """Numbers quoted in the prose: \\bv<Split><System><Measure>."""
    out = []
    tags = {"copy": "Copy", "model2-arat5": "Tfive", "model2-arabart": "Bart", "model2-arat5-notag": "TfiveN",
            "model2-arabart-notag": "BartN", "app-arat5": "AppTfive", "app-arabart": "AppBart"}
    meas = {("meaning", "meaning kept"): ("Kept", "rate"), ("meaning", "P(same meaning)"): ("Psame", "mean2"),
            ("simpler", "longest clause: words shorter"): ("Clause", "mean1"),
            ("simpler", "reading level: levels lower"): ("Level", "mean2"),
            ("simpler", "hard words: fewer"): ("Hard", "mean2"),
            ("checks", "numbers kept"): ("Num", "rate"), ("checks", "no house-rule break"): ("Rules", "rate"),
            ("behaviour", "C: easy text left unchanged"): ("C", "rate"), ("behaviour", "E1: end mark kept"): ("Eone", "rate"),
            ("behaviour", "F: letters unchanged"): ("F", "rate"), ("flags", "negation changed"): ("Neg", "rate")}
    for split, sp in (("dev", "Dev"), ("test", "Test")):
        for c, t in tags.items():
            res = load(split, c)
            for s, st in (("core", ""), ("outside", "Out"), ("held-out", "Held"), ("written", "Wri")):
                for (block, measure), (mn, kind) in meas.items():
                    e = entry(res, s, block, measure)
                    if e is None:
                        continue
                    m = value(e, kind)[0]                      # prose form: no sign on means
                    v = "pending" if e.get("complete") is False else (f"{m:.1f}" if kind == "rate" else
                                                                      f"{m:.{int(kind[-1])}f}")
                    out.append(rf"\newcommand{{\bv{sp}{st}{t}{mn}}}{{{v}}}")
        for a, b, _ in EFFECTS:
            res = load(split, f"{b}-vs-{a}")
            name = (tags[b] + "vs" + tags[a])
            for block, measure, _, _k in FX:
                e = entry(res, "core", block, measure)
                if e is None or "diff" not in e or e.get("complete") is False:
                    continue
                d, lo, hi = e["diff"]
                mn = {"meaning kept": "Kept", "longest clause: words shorter": "Clause", "C: easy text left unchanged": "C"}[measure]
                out.append(rf"\newcommand{{\bfx{sp}{name}{mn}}}{{{abs(d):.1f}}}")      # size, for the prose
                out.append(rf"\newcommand{{\bfx{sp}{name}{mn}S}}{{{d:+.1f}}}")        # signed
                out.append(rf"\newcommand{{\bfx{sp}{name}{mn}CI}}{{[{lo:+.1f}, {hi:+.1f}]}}")
    return out


def main():
    head = "test" if complete("test") else "dev"
    other = "dev" if head == "test" else "test"
    n = {"dev": (731, 129, 380), "test": (1250, 197, 749)}
    parts = ["% Generated by make_bench_v2.py -- do not edit by hand.",
             r"\newcommand{\benchheadsplit}{" + head + "}",
             r"\newcommand{\benchmeaningcomplete}{" + ("yes" if complete("test") else "no") + "}"]
    cap = (r"The v0.2 models on BayanBench v2, \textbf{{{sp}}} split, \emph{{core}} items ({c} of {a} items; {d} documents "
           r"in the split), each system run once. Meaning: the open scorer, Gemma~4 31B; a copy of the input keeps its "
           r"meaning by definition. Simpler: mean change from selection to output, over the items where there is "
           r"something to simplify. Rates in \%, means with their sign; 95\% intervals from a bootstrap over whole "
           r"documents in brackets. The two \texttt{{[S2]}} columns send the medium strength tag the model was trained "
           r"with; the two \emph{{int8 app}} columns are the quantised bundles the app downloads, which send no tag. "
           r"All outputs pass through the app's guards. Bold: the best model on each row. $n$ = items the measure "
           r"applies to.")
    parts.append(r"\newcommand{\benchheadtable}{" + table(head, "core", "tab:benchhead",
                 cap.format(sp=head, a=n[head][0], d=n[head][1], c=n[head][2])) + "}")
    parts.append(r"\newcommand{\benchothertable}{" + table(other, "core", "tab:benchother",
                 cap.format(sp=other, a=n[other][0], d=n[other][1], c=n[other][2])) + "}")
    parts.append(r"\newcommand{\benchsetstable}{" + sets_table(head, "tab:benchsets",
                 r"The four item sets on the " + head + r" split, reported side by side and never averaged; number "
                 r"of items in brackets. \emph{Core}: BAREC test documents; \emph{held-out}: news and legal text; "
                 r"\emph{outside}: web text published after every corpus we use; \emph{written}: medicine-leaflet "
                 r"sentences written for the benchmark.") + "}")
    parts.append(r"\newcommand{\benchefftable}{" + effects_table(head, "core", "tab:benchfx",
                 r"Paired effects on the " + head + r" split (core items): one change at a time, same items. "
                 r"Differences in points (rates) or words (clause), with 95\% document-bootstrap intervals; "
                 r"$^{*}$ = the interval excludes zero.") + "}")
    # trade-off figure: meaning kept against words cut from the longest clause, core items, both splits
    for split, sp in (("dev", "Dev"), ("test", "Test")):
        pts = []
        for c in SYSTEMS:
            res = load(split, c)
            k, w = entry(res, "core", "meaning", "meaning kept"), entry(res, "core", "simpler", "longest clause: words shorter")
            if k is None or w is None or k.get("complete") is False:
                continue
            (km, klo, khi), (wm, wlo, whi) = k["rate"], w["mean"]
            pts.append(f"{{{wm:.2f}/{km:.1f}/{wm - wlo:.2f}/{whi - wm:.2f}/{km - klo:.1f}/{khi - km:.1f}/{STYLE[c]}}}")
        parts.append(rf"\newcommand{{\tradeoff{sp}}}{{" + ",".join(pts) + "}")
        if split == head:
            parts.append(r"\newcommand{\tradeoffH}{" + ",".join(pts) + "}")
    mac = macros()
    sp = head.capitalize()
    # \bvH... and \bfxH...: the same numbers on the headline split, so the prose follows the headline table
    for line in list(mac):
        for pre in (r"\newcommand{\bv" + sp, r"\newcommand{\bfx" + sp):
            if line.startswith(pre):
                mac.append(line.replace(pre, pre[:-len(sp)] + "H", 1))
    # ranges over the six model systems (copy excluded), headline split, core items: \bvHmin<M> / \bvHmax<M>
    models = [c for c in SYSTEMS if c != "copy"]
    for (block, measure), (mn, kind) in {("meaning", "meaning kept"): ("Kept", "rate"),
                                         ("simpler", "longest clause: words shorter"): ("Clause", "mean1"),
                                         ("simpler", "reading level: levels lower"): ("Level", "mean2"),
                                         ("simpler", "hard words: fewer"): ("Hard", "mean2"),
                                         ("checks", "numbers kept"): ("Num", "rate"),
                                         ("behaviour", "C: easy text left unchanged"): ("C", "rate"),
                                         ("behaviour", "E1: end mark kept"): ("Eone", "rate"),
                                         ("behaviour", "F: letters unchanged"): ("F", "rate")}.items():
        vals = [value(e, kind)[0] for e in (entry(load(head, c), "core", block, measure) for c in models)
                if e is not None and e.get("complete") is not False]
        if vals:
            f = (lambda x: f"{x:.1f}") if kind == "rate" else (lambda x: f"{x:.{int(kind[-1])}f}")
            mac.append(rf"\newcommand{{\bvHmin{mn}}}{{{f(min(vals))}}}")
            mac.append(rf"\newcommand{{\bvHmax{mn}}}{{{f(max(vals))}}}")
    parts += mac
    Path("bench_v2.tex").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("wrote bench_v2.tex; headline split:", head)


if __name__ == "__main__":
    main()
