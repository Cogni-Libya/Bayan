"""Write bench_results.tex: model 2 on BayanBench, code tier, with 95% cluster-bootstrap intervals.

    python make_bench_results.py ~/MyProjects/Bayan/data/processed/bench

Reads the bench's items, the model outputs (preds/<split>/<system>.jsonl, field "app" = what the reader sees after the
app's retention fallback and punctuation fix) and the reading-level cache. Every measure is computed with the bench's own
functions (lib.py, ease.py), exactly as codeonly.py does; nothing is averaged across measures or item sets."""
import collections, json, random, sys
from pathlib import Path

BENCH = Path(sys.argv[1]).expanduser()
sys.path.insert(0, str(BENCH))
from lib import norm, numbers, negations, longest_clause, end_mark, rule_breaks, retention, item_set  # noqa: E402
from ease import samer_lexicon, hard_words, tkey  # noqa: E402

LEX = samer_lexicon()
EASE = {json.loads(l)["key"]: json.loads(l) for l in open(BENCH / "ease/cache.jsonl", encoding="utf-8")}
SYSTEMS = {  # bench name: label in the report
    "copy": "Copy the input",
    "model2-arat5": r"AraT5v2, \texttt{[S2]}",
    "model2-arabart": r"AraBART, \texttt{[S2]}",
    "model2-arat5-notag": "AraT5v2, no tag",
    "model2-arabart-notag": "AraBART, no tag",
    "app-arat5": "AraT5v2, int8 app",
    "app-arabart": "AraBART, int8 app",
}


def measures(it, out):
    """Code-tier measures for one item, as in the bench's codeonly.py. None = the measure does not apply."""
    src, tr = it["source"], it["track"]
    if tr == "F":
        return {"F": norm(out) == norm(src)}
    m = {"num": numbers(out) == numbers(src) if numbers(src) else None,
         "neg": negations(out) == negations(src) if negations(src) else None,
         "rules": not rule_breaks(src, out)}
    if tr == "C":
        m["C"] = norm(out) == norm(src)
    else:
        m["kept"] = retention(src, out) >= 0.6
        hs = hard_words(src, LEX)
        m["hard"] = hard_words(out, LEX) < hs if hs else None
        es, eo = EASE.get(tkey(src)), EASE.get(tkey(out))
        m["level"] = eo["level_max"] < es["level_max"] if es and eo and es["level_max"] >= 10 else None
    if tr == "B":
        m["B"] = longest_clause(out) <= 15
        m["Bedit"] = norm(out) != norm(src)
    if tr == "E1":
        m["E1"] = end_mark(out) == end_mark(src)
    if tr == "E3":
        m["E3"] = longest_clause(out) <= 15
    return m


def ci(xs, n=2000):
    """Rate and 95% interval, bootstrapping whole documents (items of one document pass or fail together)."""
    if not xs:
        return None
    by = collections.defaultdict(list)
    for d, v in xs:
        by[d].append(v)
    groups, rng = list(by.values()), random.Random(1)
    mean = sum(v for _, v in xs) / len(xs)
    bs = sorted(sum(sum(g) for g in s) / sum(len(g) for g in s) for s in (rng.choices(groups, k=len(groups)) for _ in range(n)))
    return 100 * mean, 100 * bs[int(0.025 * n)], 100 * bs[int(0.975 * n)], len(xs)


def load(split, set_=None):
    items = {json.loads(l)["id"]: json.loads(l) for l in open(BENCH / f"items/{split}.jsonl", encoding="utf-8")}
    items = {i: it for i, it in items.items() if set_ is None or item_set(it) == set_}
    per = {}
    for s in SYSTEMS:
        p = BENCH / f"preds/{split}/{s}.jsonl"
        if not p.exists():
            continue
        per[s] = collections.defaultdict(dict)
        for l in open(p, encoding="utf-8"):
            r = json.loads(l)
            it = items.get(r["id"])
            if it is None:
                continue
            for k, v in measures(it, r["app"]).items():
                if v is not None:
                    per[s][k][r["id"]] = (it["doc"], int(v))
    return items, per


def paired(a, b):
    """a - b in points over the items both have, with a document-clustered 95% interval."""
    common = sorted(set(a) & set(b))
    return ci([(a[i][0], a[i][1] - b[i][1]) for i in common])


ROWS = [  # key, label, group
    ("B", r"No clause over 15 words (B, long clauses)", "Easier"),
    ("E3", r"No clause over 15 words (E3, 40+ words)", "Easier"),
    ("hard", r"Fewer hard words (items with any)", "Easier"),
    ("level", r"Lower reading level (sources at level 10+)", "Easier"),
    ("kept", r"Kept 60\%+ of the source's words", "Faithful"),
    ("num", r"Numbers kept (items with numbers)", "Faithful"),
    ("neg", r"Negations kept (items with a negation)", "Faithful"),
    ("rules", r"No house-rule break", "Faithful"),
    ("C", r"Easy text left unchanged (C)", "Restraint"),
    ("E1", r"Cut-off selection keeps its ending (E1)", "Restraint"),
    ("F", r"Protected text: letters unchanged (F)", "Restraint"),
]


def cell(r, bold=False):
    if r is None:
        return "---"
    m, lo, hi, _ = r
    v = f"{m:.1f}"
    v = r"\textbf{" + v + "}" if bold else v
    if lo == hi:                                  # degenerate interval (copy): show the rate alone
        return v
    return r"\makecell{" + v + r"\\[-2pt]{\tiny[" + f"{lo:.0f}--{hi:.0f}" + "]}}"


def table(split, cols, label, caption):
    items, per = load(split)
    out = [r"\begin{table}[h]", r"\small", r"\caption{" + caption + "}", r"\label{" + label + "}",
           r"\begin{tabularx}{\linewidth}{|L|" + "C{16.2mm}|" * len(cols) + "C{7mm}|}", r"\hline",
           r"\head{Measure (pass rate, \%)} & " + " & ".join(r"\head{" + SYSTEMS[c] + "}" for c in cols) + r" & \head{$n$} \\ \hline"]
    group = None
    for k, lab, g in ROWS:
        if g != group:
            out.append(r"\multicolumn{" + str(len(cols) + 2) + r"}{|l|}{\cellcolor{sichead}\textbf{" + g + r"}} \\ \hline")
            group = g
        rs = [ci(list(per[c][k].values())) if c in per else None for c in cols]
        models = [r for c, r in zip(cols, rs) if c != "copy" and r]
        best = max(r[0] for r in models) if models else None
        cells = [cell(r, bold=(c != "copy" and r is not None and abs(r[0] - best) < 1e-9)) for c, r in zip(cols, rs)]
        n = next((r[3] for r in rs if r), 0)
        out.append(lab + " & " + " & ".join(cells) + f" & {n:,}" + r" \\ \hline")
    out += [r"\end{tabularx}", r"\end{table}"]
    return "\n".join(out)


def sets_table(split, systems, label, caption):
    out = [r"\begin{table}[h]", r"\small", r"\caption{" + caption + "}", r"\label{" + label + "}",
           r"\begin{tabularx}{\linewidth}{|L|C{21mm}|C{21mm}|C{21mm}|C{21mm}|}", r"\hline",
           r"\head{System and measure} & \head{Core} & \head{Held-out} & \head{Outside} & \head{Written} \\ \hline"]
    loaded = {s: load(split, s)[1] for s in ("core", "held-out", "outside", "written")}
    for sysname in systems:
        out.append(r"\multicolumn{5}{|l|}{\cellcolor{sichead}\textbf{" + SYSTEMS[sysname] + r"}} \\ \hline")
        for k, lab in (("B", "No clause over 15 words (B)"), ("hard", "Fewer hard words"),
                       ("level", "Lower reading level"), ("kept", r"Kept 60\%+ of words"), ("C", "Easy text left unchanged")):
            cells = []
            for s in ("core", "held-out", "outside", "written"):
                d = loaded[s].get(sysname, {}).get(k, {})
                r = ci(list(d.values()))
                cells.append("---" if r is None else f"{r[0]:.1f}" + r"\,{\tiny(" + f"{r[3]}" + ")}")
            out.append(lab + " & " + " & ".join(cells) + r" \\ \hline")
    out += [r"\end{tabularx}", r"\end{table}"]
    return "\n".join(out)


def effects(split):
    """Paired effects: the strength tag (tagged -> untagged, same model) and int8 export (untagged PyTorch -> int8 app)."""
    _, per = load(split)
    rows = []
    for a, b, what in (("model2-arat5", "model2-arat5-notag", r"AraT5v2: drop the \texttt{[S2]} tag"),
                       ("model2-arabart", "model2-arabart-notag", r"AraBART: drop the \texttt{[S2]} tag"),
                       ("model2-arat5-notag", "app-arat5", "AraT5v2: PyTorch fp32 $\\rightarrow$ int8 ONNX"),
                       ("model2-arabart-notag", "app-arabart", "AraBART: PyTorch fp32 $\\rightarrow$ int8 ONNX")):
        if a not in per or b not in per:
            continue
        cells = []
        for k in ("B", "hard", "kept", "C"):
            r = paired(per[b][k], per[a][k])
            if r is None:
                cells.append("---")
                continue
            m, lo, hi, _ = r
            star = r"$^{*}$" if lo > 0 or hi < 0 else ""
            cells.append(f"{m:+.1f}{star}" + r"\,{\tiny[" + f"{lo:+.0f}, {hi:+.0f}" + "]}")
        rows.append(what + " & " + " & ".join(cells) + r" \\ \hline")
    return rows


def main():
    parts = ["% Generated by make_bench_results.py -- do not edit by hand."]
    cols = ["copy", "model2-arat5", "model2-arabart", "app-arat5", "app-arabart"]
    parts.append(r"\newcommand{\benchtesttable}{" + table(
        "test", cols, "tab:benchtest",
        r"Model~2 on the BayanBench \textbf{test} split (1,250 items, 197 documents), run once, code tier. "
        r"Pass rates in \%, with the 95\% interval from a bootstrap over whole documents in brackets. "
        r"The first two model columns send the \texttt{[S2]} (medium) strength tag the model was trained with; the "
        r"two \emph{int8 app} columns are the quantised bundles the app downloads, which send no tag. All outputs pass "
        r"through the app's retention fallback and punctuation fix. Bold: the best model on each row. "
        r"$n$ = items the measure applies to.") + "}")
    parts.append(r"\newcommand{\benchdevtable}{" + table(
        "dev", cols, "tab:benchdev",
        r"The same measures on the BayanBench \textbf{dev} split (731 items, 129 documents), for comparison with "
        r"\autoref{tab:benchtest}.") + "}")
    parts.append(r"\newcommand{\benchsetstable}{" + sets_table(
        "test", ["model2-arat5", "app-arabart"], "tab:benchsets",
        r"Model~2 on the four BayanBench item sets (test split), pass rate in \%, number of items in brackets. "
        r"\emph{Core}: BAREC test documents; \emph{held-out}: news and legal text; \emph{outside}: 344 web sentences "
        r"published after every corpus we use; \emph{written}: medicine-leaflet sentences. The sets are reported side by "
        r"side and never averaged.") + "}")
    eff = effects("test")
    parts.append(r"\newcommand{\benchefftable}{\begin{table}[h]\small\caption{Paired effects on the test split, "
                 r"in points, with 95\% document-bootstrap intervals; $^{*}$ = the interval excludes zero. "
                 r"Same items, same model, one change at a time.}\label{tab:benchfx}"
                 r"\begin{tabularx}{\linewidth}{|L|C{21mm}|C{21mm}|C{21mm}|C{21mm}|}\hline"
                 r"\head{Change} & \head{No clause over 15 (B)} & \head{Fewer hard words} & \head{Kept 60\%+ of words} "
                 r"& \head{Easy text unchanged (C)} \\ \hline " + "\n".join(eff) + r"\end{tabularx}\end{table}}")
    # headline macros quoted in the prose
    _, per = load("test")
    def m(s, k):
        r = ci(list(per[s][k].values()))
        return f"{r[0]:.1f}" if r else "---"
    for s, tag in (("model2-arat5", "Tfive"), ("model2-arabart", "Bart"), ("app-arat5", "AppTfive"), ("app-arabart", "AppBart")):
        for k, name in (("B", "B"), ("hard", "Hard"), ("level", "Level"), ("kept", "Kept"), ("C", "C"), ("num", "Num"),
                        ("neg", "Neg"), ("E1", "Eone"), ("F", "F"), ("E3", "Ethree")):
            parts.append(rf"\newcommand{{\bt{tag}{name}}}{{{m(s, k)}}}")
    Path("bench_results.tex").write_text("\n".join(parts) + "\n", encoding="utf-8")
    print("wrote bench_results.tex")


if __name__ == "__main__":
    main()
