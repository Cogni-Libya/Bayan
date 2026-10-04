"""All tables (build/tab/*.tex), the numbers quoted in the text (build/tab/macros.tex) and the Arabic examples."""
import json, math, re

import common as C
from common import SHIP, APP, label, val, diff, summ, analysis

TAB = C.BUILD / "tab"
NAN = float("nan")


def esc(s):
    return re.sub(r"([%&_#$])", r"\\\1", str(s))


def f(v, kind="mean", d=2):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "--"
    return f"{v:.{d}f}" if kind == "mean" else f"{v:.0f}"


def ci_cell(t, kind="mean", d=2):
    v, lo, hi = t
    if math.isnan(v):
        return "--"
    if kind == "mean":
        return f"{v:.{d}f}\\,{{\\tiny[{lo:.{d}f}, {hi:.{d}f}]}}"
    return f"{v:.0f}\\,{{\\tiny[{lo:.0f}, {hi:.0f}]}}"


def star(t, lower_better=False):
    d, lo, hi = t
    if math.isnan(d):
        return ""
    if lo > 0:
        return "$\\uparrow$" if not lower_better else "$\\Downarrow$"
    if hi < 0:
        return "$\\downarrow$" if not lower_better else "$\\Uparrow$"
    return ""


def write(name, s):
    TAB.mkdir(parents=True, exist_ok=True)
    (TAB / f"{name}.tex").write_text(s, encoding="utf-8")


def keys_for(split):
    return [k for k in C.S.SYSTEMS if C.card(split, k)]


# ------------------------------------------------------------ systems
def systems():
    rows = []
    for k, (lab, g, desc, _, _) in C.S.SYSTEMS.items():
        rows.append(f"{esc(lab)} & {esc(g)} & {esc(desc)} \\\\")
    write("systems", "\\begin{longtable}{p{4.6cm}p{2.0cm}p{8.2cm}}\n\\toprule System & Group & What it is \\\\ \\midrule\\endhead\n"
          + "\n".join(rows) + "\n\\bottomrule\n\\end{longtable}\n")


# ------------------------------------------------------------ leaderboards
LEAD = [("meaning", "P(same meaning)", "P(same)", "mean", 2, False),
        ("meaning", "meaning kept", "Kept\\%", "rate", 0, False),
        ("meaning", "meaning kept and simpler", "Joint\\%", "rate", 0, False),
        ("simpler", "longest clause: words shorter", "Clause$\\downarrow$", "mean", 1, False),
        ("simpler", "reading level: levels lower", "Level$\\downarrow$", "mean", 2, False),
        ("simpler", "hard words: fewer", "Hard w.$\\downarrow$", "mean", 2, False),
        ("checks", "numbers kept", "Num.\\%", "rate", 0, False),
        ("behaviour", "C: easy text left unchanged", "Easy=\\%", "rate", 0, False),
        ("behaviour", "F: letters unchanged", "Prot.\\%", "rate", 0, False),
        ("flags", "negation changed", "Neg.$\\Delta$\\%", "rate", 0, True)]


def leaderboard(split, st="core", keys=None, name=None, with_extra=True):
    keys = keys or keys_for(split)
    vals = {k: [val(split, k, b, n, st) for b, n, *_ in LEAD] for k in keys}
    best = []
    for j, (b, n, _, kind, d, lower) in enumerate(LEAD):
        col = [vals[k][j][0] for k in keys if k not in ("copy",) and not math.isnan(vals[k][j][0])]
        best.append((min(col) if lower else max(col)) if col else None)
    head = " & ".join(h for _, _, h, *_ in LEAD)
    extra_h = " & Contra\\% & Arabic & Unch.\\%" if with_extra else ""
    rows = []
    for k in keys:
        cells = []
        for j, (b, n, _, kind, d, lower) in enumerate(LEAD):
            v = vals[k][j][0]
            c = f(v, kind, d)
            if best[j] is not None and not math.isnan(v) and round(v, d) == round(best[j], d) and k != "copy":
                c = f"\\textbf{{{c}}}"
            cells.append(c)
        if with_extra:
            s = summ(split, k, st)
            cr = s.get("contradict_rate_changed", [NAN])[0]
            cells += [f(cr, "rate"), f(s.get("arabic", [NAN])[0], "mean"), f(s.get("unchanged", [NAN])[0], "rate")]
        nm = esc(label(k))
        if k == SHIP:
            nm = f"\\textbf{{{nm}}}"
        rows.append(f"{nm} & " + " & ".join(cells) + " \\\\")
        if k in ("app-arabart", "v1-arabart", "m3-dpo-net", "m3-q-b4-net", "rt-q-b4-net"):
            rows.append("\\midrule")
    while rows and rows[-1] == "\\midrule":
        rows.pop()
    ncol = len(LEAD) + (3 if with_extra else 0)
    write(name or f"lead_{split}_{st}",
          f"\\begin{{tabular}}{{l{'r' * ncol}}}\n\\toprule System & {head}{extra_h} \\\\\n\\midrule\n" + "\n".join(rows) +
          "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------ the ship gate: paired differences vs today's app
def gate():
    out = []
    for split in ("dev", "test"):
        out.append(f"\\multicolumn{{4}}{{l}}{{\\textit{{{split} split}}}} \\\\")
        for b, n, lab, kind in C.MEASURES:
            e = C.entry(split, SHIP, b, n)
            ea = C.entry(split, APP, b, n)
            if not e or not ea:
                continue
            v = e.get("rate") or e.get("mean"); va = ea.get("rate") or ea.get("mean")
            d = e.get("diff", [NAN] * 3)
            low = n in C.LOWER_BETTER
            kd = 2 if kind == "mean" else 0
            s = star(tuple(d), low)
            verdict = ""
            if s:
                good = (d[1] > 0) != low
                verdict = "\\textcolor{good}{better}" if good else "\\textcolor{bad}{worse}"
            out.append(f"{esc(lab)} & {f(va[0], kind, kd)} & {f(v[0], kind, kd)} & "
                       f"{d[0]:+.{kd}f} [{d[1]:+.{kd}f}, {d[2]:+.{kd}f}] {verdict} \\\\")
        out.append("\\midrule")
    write("gate", "\\begin{longtable}{lrrl}\n\\toprule Measure (core items) & App today & Ship candidate & Paired difference [95\\% CI] \\\\ \\midrule\\endhead\n"
          + "\n".join(out[:-1]) + "\n\\bottomrule\n\\end{longtable}\n")


def pairdiff():
    """Paired differences against today's app for every system (test, core)."""
    ms = [("meaning", "P(same meaning)", "P(same)", 2), ("meaning", "meaning kept", "Kept (pts)", 0),
          ("simpler", "longest clause: words shorter", "Clause", 1), ("simpler", "reading level: levels lower", "Level", 2),
          ("checks", "numbers kept", "Numbers (pts)", 0)]
    for split in ("dev", "test"):
        rows = []
        for k in keys_for(split):
            if k == APP:
                continue
            cells = []
            for b, n, _, d in ms:
                t = diff(split, k, b, n)
                cells.append("--" if math.isnan(t[0]) else f"{t[0]:+.{d}f}{star(t)}")
            rows.append(f"{esc(label(k))} & " + " & ".join(cells) + " \\\\")
        write(f"pairdiff_{split}", "\\begin{longtable}{l" + "r" * len(ms) + "}\n\\toprule System $-$ app & " + " & ".join(m[2] for m in ms)
              + " \\\\ \\midrule\\endhead\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{longtable}\n")


# ------------------------------------------------------------ per item set (appendix)
def per_set():
    for split in ("dev", "test"):
        for st in C.SETS:
            leaderboard(split, st, name=f"lead_{split}_{st.replace('-', '')}", with_extra=False)


# ------------------------------------------------------------ the scorer vs humans
def judge():
    hv = analysis()["human_validation"]
    best = max(hv["sweep"], key=lambda s: s["bal"])
    at5 = min(hv["sweep"], key=lambda s: abs(s["t"] - 0.5))
    rows = [f"Gemma 31B P(same) vs majority ``same'' & AUC & {hv['auc_same']:.3f} & {hv['n_pos']} same / {hv['n_neg']} changed \\\\",
            f"Gemma 31B P(same) vs majority ``major'' & AUC & {hv['auc_major']:.3f} & \\\\",
            f"At the frozen threshold 0.5 & accuracy / balanced & {at5['acc']:.3f} / {at5['bal']:.3f} & same kept {100 * at5['tpr']:.0f}\\%, changes caught {100 * at5['tnr']:.0f}\\% \\\\",
            f"Best balanced threshold & {best['t']:.2f} & {best['bal']:.3f} & \\\\",
            f"Gemma ``Arabic correct'' vs human Arabic ok & AUC & {hv['auc_arabic']:.3f} & n={hv['n_arabic']} \\\\",
            f"Gemma ``easier'' vs human easier & AUC & {hv['auc_ease']:.3f} & n={hv['n_ease']} \\\\"]
    if "auc_mimo" in hv:
        mr = hv["mimo_result"]
        rows.append(f"MiMo (second-judge pilot) vs majority ``same'' & AUC & {hv['auc_mimo']:.3f} & sided with humans on {mr['mimo_sides_with_humans']}/{mr['disagreements']} Gemma disagreements \\\\")
    for ax, nm in (("m", "meaning"), ("a", "Arabic"), ("e", "ease")):
        a = hv["alpha"][ax]
        rows.append(f"Inter-rater agreement, {nm} & Krippendorff $\\alpha$ (nominal / ordinal / binary) & "
                    f"{a['nominal']:.2f} / {a['ordinal']:.2f} / {a['binary']:.2f} & {a['units']} items with 2+ raters \\\\")
    write("judge", "\\begin{tabular}{p{5.6cm}p{3.6cm}rp{4.4cm}}\n\\toprule Comparison & Statistic & Value & Note \\\\ \\midrule\n"
          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------ reference-based (SARI) from the all-systems comparison
def refsets():
    p = C.S.ROOT / "compare/report/report.json"
    if not p.exists():
        return
    R = json.load(open(p))
    names = {"copy": "Copy", "model1": "Model 1", "model2-arat5": "Model 2 AraT5 [S2]", "model2-arat5-notag": "Model 2 AraT5 no tag",
             "model2-arabart": "Model 2 AraBART [S2]", "model2-arabart-notag": "Model 2 AraBART no tag",
             "v1-mle-arabart": "AraBART on corpus v1", "model3-arat5-v1": "Model 3 greedy", "model3-dpo": "Model 3 + DPO"}
    rows = []
    for k, nm in names.items():
        c = []
        for rs in ("v1_dev", "v1_test", "samer_test"):
            r = R["refsets"][rs].get(k)
            c += [f(r["sari_changed"], "mean", 1), f(100 * r["copy_changed"], "rate")] if r else ["--", "--"]
        q = R["quality"]["v1_test"].get(k, {})
        c += [f(100 * q["new_words_not_in_barec"], "mean", 1) if q else "--", f(100 * q["repeated_word_or_3gram"], "mean", 1) if q else "--"]
        rows.append(f"{esc(nm)} & " + " & ".join(c) + " \\\\")
    write("refsets", "\\begin{tabular}{lrrrrrrrr}\n\\toprule & \\multicolumn{2}{c}{Corpus v1 dev} & \\multicolumn{2}{c}{Corpus v1 test} & \\multicolumn{2}{c}{SAMER test (L3+L4 refs)} & \\multicolumn{2}{c}{Quality, v1 test} \\\\\n"
          "\\cmidrule(lr){2-3}\\cmidrule(lr){4-5}\\cmidrule(lr){6-7}\\cmidrule(lr){8-9} System & SARI & Copy\\% & SARI & Copy\\% & SARI & Copy\\% & Non-word\\% & Repeat\\% \\\\ \\midrule\n"
          + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------ device and int8
def device():
    F = json.load(open(C.HERE / "facts.json"))
    rows = [f"{esc(r['name'])} & {r['size_mb']} & {r['s_per_sentence']:.2f} & {esc(r['hw'])} \\\\" for r in F["device"]]
    write("device", "\\begin{tabular}{lrrp{6cm}}\n\\toprule Model & MB & s/sentence & Hardware, decoding \\\\ \\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")
    rows = [f"{esc(r['cpu'])} & {esc(r['recipe'])} & {r['match']} & {esc(r['verdict'])} \\\\" for r in F["int8_cpu"]]
    write("int8", "\\begin{tabular}{p{3.6cm}p{4.2cm}rp{4.0cm}}\n\\toprule CPU & int8 recipe & = PyTorch & Output \\\\ \\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")
    rows = [f"\\texttt{{{esc(r['repo'])}}} & {esc(r['what'])} & {r['size']} \\\\" for r in F["bundles"]]
    write("bundles", "\\begin{tabular}{lp{7cm}r}\n\\toprule Hugging Face repo (private) & Contents & Size \\\\ \\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


def training():
    T = analysis()["training"]
    sel = (T.get("retrain_selection") or {}).get("table", {})
    rows = []
    for k, v in sel.items():
        rows.append(f"{esc(k.replace('checkpoint-', 'step '))} & {f(v['arabic'], 'mean', 3)} & {f(v['p_same'], 'mean', 3)} & {f(v['sari'], 'mean', 1) if v['sari'] else '--'} \\\\")
    write("retrain_sel", "\\begin{tabular}{lrrr}\n\\toprule Checkpoint & Gemma Arabic & P(same) & SARI \\\\ \\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n")


# ------------------------------------------------------------ Arabic examples
def examples():
    E = analysis()["examples"]
    titles = {"good": "Good simplifications by the ship candidate", "net": "Safety-net catches (the plain output was replaced by the source)",
              "restraint": "Restraint: easy text the app changed and the ship candidate left alone",
              "slip": "Meaning slips (Gemma P(same) $<$ 0.2)", "grammar": "Grammar problems (Gemma ``Arabic correct'' $<$ 0.2, meaning kept)"}
    out = []
    for k in ("good", "net", "restraint", "slip", "grammar"):
        if not E.get(k):
            continue
        out.append(f"\\subsection*{{{titles[k]}}}")
        for r in E[k][:2]:
            sc = []
            for nm, key in (("P(same)", "p_same"), ("Arabic", "arabic"), ("clause $-$words", "clause")):
                if r.get(key) is not None:
                    sc.append(f"{nm} {r[key]:.2f}" if key != "clause" else f"{nm} {r[key]:.0f}")
            out.append("\\begin{exbox}{" + esc(r["id"]) + f" ({esc(r['domain'])}, track {esc(r['track'])}): " + ", ".join(sc) + "}")
            out.append("\\exrow{Source}{" + ar(r["source"]) + "}")
            if k == "net":
                out.append("\\exrow{Model output}{" + ar(r["ship_plain"]) + "}")
                out.append("\\exrow{Shown (net)}{" + ar(r["ship"]) + "}")
            else:
                out.append("\\exrow{Ship candidate}{" + ar(r["ship"]) + "}")
            out.append("\\exrow{App today}{" + ar(r["app"]) + "}")
            out.append("\\end{exbox}")
    write("examples", "\n".join(out) + "\n")


def ar(t):
    t = t.replace("\\", "").replace("{", "(").replace("}", ")")
    return esc(t).replace("~", " ").replace("^", "")


# ------------------------------------------------------------ numbers quoted in the text
def macros():
    m = {}

    def put(name, v, d=2):
        m[name] = "--" if v is None or (isinstance(v, float) and math.isnan(v)) else (f"{v:.{d}f}" if d else f"{v:.0f}")
    for split, S_ in (("dev", "Dev"), ("test", "Test")):
        for k, K in ((SHIP, "Ship"), (APP, "App"), ("m3-net", "Mnet"), ("m3", "Mthree"), ("m2-arat5-nt", "Mtwo"), ("rt-q-b4-net", "Rt"), ("m3-b4-net", "Mbfour")):
            put(f"{S_}{K}Psame", val(split, k, "meaning", "P(same meaning)")[0])
            put(f"{S_}{K}Kept", val(split, k, "meaning", "meaning kept")[0], 0)
            put(f"{S_}{K}Clause", val(split, k, "simpler", "longest clause: words shorter")[0], 1)
            put(f"{S_}{K}Level", val(split, k, "simpler", "reading level: levels lower")[0])
            put(f"{S_}{K}Num", val(split, k, "checks", "numbers kept")[0], 0)
            put(f"{S_}{K}Easy", val(split, k, "behaviour", "C: easy text left unchanged")[0], 0)
            put(f"{S_}{K}Unch", summ(split, k).get("unchanged", [NAN])[0], 0)
            put(f"{S_}{K}Arabic", summ(split, k).get("arabic", [NAN])[0])
            ps = [r["p_same"] for r in analysis()["per_system"][split][k]["items"].values() if r["set"] == "core" and not r["copy"] and "p_same" in r]
            put(f"{S_}{K}PsameChanged", sum(ps) / len(ps) if ps else NAN)
        for b, n, nm, d in (("meaning", "P(same meaning)", "Psame", 2), ("meaning", "meaning kept", "Kept", 0),
                            ("simpler", "longest clause: words shorter", "Clause", 1), ("simpler", "reading level: levels lower", "Level", 2)):
            t = diff(split, SHIP, b, n)
            m[f"{S_}Diff{nm}"] = "--" if math.isnan(t[0]) else f"{t[0]:+.{d}f} [{t[1]:+.{d}f}, {t[2]:+.{d}f}]"
    hv = analysis()["human_validation"]
    put("JudgeAUC", hv["auc_same"]); put("AlphaMeaning", hv["alpha"]["m"]["binary"]); put("AlphaArabic", hv["alpha"]["a"]["binary"]); put("AlphaEase", hv["alpha"]["e"]["binary"])
    put("NSystems", len(C.S.SYSTEMS), 0)
    s = "\n".join(f"\\newcommand{{\\{k}}}{{{v}}}" for k, v in sorted(m.items()))
    write("macros", s + "\n")


if __name__ == "__main__":
    systems()
    for sp in ("dev", "test"):
        leaderboard(sp)
    for fn in (gate, pairdiff, per_set, judge, refsets, device, training, examples, macros):
        try:
            fn(); print("ok", fn.__name__)
        except Exception as e:
            import traceback; traceback.print_exc(); print("FAILED", fn.__name__, e)
