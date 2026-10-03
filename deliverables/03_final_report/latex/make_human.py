"""Write human.tex: the human rating round of BayanBench v2 (#48), and the open meaning scorer checked against it.

    python make_human.py <bayanbench-data folder>

Reads ratings/human_ratings_v2.jsonl (290 tasks: 245 single outputs, 45 comparisons; dev split, core and outside
items) and items/dev.jsonl (for each item's document). Raters are reported by role, not by name.

Sampling (build_h2.py): 35 changed outputs per system drawn evenly ("even", 210), plus 35 drawn near the scorer's
0.5 cut-off ("near"). Per-system rates use the even sample only, so the cut-off oversampling does not skew them;
agreement and the scorer check use all 245. Meaning "kept" = a strict majority of the task's raters said "same
meaning" (a tie is not kept). Intervals: 95%, bootstrap over whole documents (2,000 resamples), as in the bench."""
import collections, itertools, json, random, sys
from pathlib import Path

D = Path(sys.argv[1]).expanduser()
rows = [json.loads(l) for l in open(D / "ratings/human_ratings_v2.jsonl", encoding="utf-8")]
doc = {json.loads(l)["id"]: json.loads(l)["doc"] for l in open(D / "items/dev.jsonl", encoding="utf-8")}
TEAM = ["sanad", "ahmed", "mohammed", "abdulrahman", "marwan"]
READER = "ibrahim"
SYSTEMS = {"app-arat5": "AraT5v2, int8 app", "model2-arat5-notag": "AraT5v2, no tag",
           "model2-arat5": r"AraT5v2, \texttt{[S2]}", "app-arabart": "AraBART, int8 app",
           "model2-arabart-notag": "AraBART, no tag", "model2-arabart": r"AraBART, \texttt{[S2]}"}
ORD = {"m": {"same": 0, "minor": 1, "major": 2}, "a": {"ok": 0, "minor": 1, "major": 2},
       "e": {"easier": 0, "same": 1, "harder": 2}}
singles = [r for r in rows if r["kind"] == "single"]
pairs = [r for r in rows if r["kind"] == "pair"]
team = lambda r, q: [r["ratings"][n][q] for n in TEAM if q in r["ratings"].get(n, {})]
maj = lambda vals, v: bool(vals) and sum(x == v for x in vals) > len(vals) / 2


def alpha(q):
    """Krippendorff's alpha, interval metric on the 0-2 ranks, over tasks with two or more team raters."""
    units = [[ORD[q][v] for v in team(r, q)] for r in singles]
    units = [u for u in units if len(u) > 1]
    vals = [x for u in units for x in u]; n = len(vals)
    do = sum(sum((a - b) ** 2 for a, b in itertools.permutations(u, 2)) / (len(u) - 1) for u in units) / n
    de = sum((a - b) ** 2 for a, b in itertools.permutations(vals, 2)) / (n * (n - 1))
    return 1 - do / de, len(units)


def exact(q):
    pr = [(a, b) for r in singles for a, b in itertools.combinations(team(r, q), 2)]
    return 100 * sum(a == b for a, b in pr) / len(pr), len(pr)


def auc(lab):
    pos = [p for p, y in lab if y]; neg = [p for p, y in lab if not y]
    return sum((p > n) + 0.5 * (p == n) for p in pos for n in neg) / (len(pos) * len(neg))


def boot(lab_doc, f, n=2000):
    """95% interval of f over a bootstrap of whole documents; lab_doc = [(document, x)]."""
    by = collections.defaultdict(list)
    for d, x in lab_doc:
        by[d].append(x)
    groups, rng, out = list(by.values()), random.Random(1), []
    for _ in range(n):
        s = [x for g in rng.choices(groups, k=len(groups)) for x in g]
        try:
            out.append(f(s))
        except ZeroDivisionError:
            pass
    out.sort()
    return out[int(0.025 * len(out))], out[int(0.975 * len(out))]


def rate_ci(lab_doc):
    m = 100 * sum(x for _, x in lab_doc) / len(lab_doc)
    lo, hi = boot(lab_doc, lambda s: 100 * sum(s) / len(s))
    return m, lo, hi


rated = [r for r in singles if team(r, "m")]
kept = {r["task"]: maj(team(r, "m"), "same") for r in rated}
lost_major = {r["task"]: maj(team(r, "m"), "major") for r in rated}

M = {}                                                   # macro name -> value
M["hTasks"], M["hSingles"], M["hPairs"] = len(rows), len(singles), len(pairs)
M["hDocs"] = len({doc[r["item"]] for r in singles})
M["hEven"] = sum(r["stratum"] == "even" for r in singles)
M["hNear"] = sum(r["stratum"] == "near" for r in singles)
M["hShared"] = sum(len(team(r, "m")) >= 3 for r in singles)
for q, name in (("m", "Meaning"), ("a", "Arabic"), ("e", "Ease")):
    a, u = alpha(q); M[f"hAlpha{name}"] = f"{a:.2f}"; M[f"hAlphaUnits"] = u
    e, _ = exact(q); M[f"hExact{name}"] = f"{e:.0f}"
M["hKept"] = sum(kept.values()); M["hRated"] = len(rated)

# the scorer against the human verdicts
scorer_rows = []
for name, lab_f, key in (("majority ``same meaning''", lambda r: kept[r["task"]], "Same"),
                         ("majority not ``major change'' (a minor change counts as kept)",
                          lambda r: not lost_major[r["task"]], "NotMajor"),
                         ("every rater ``same meaning''", lambda r: all(v == "same" for v in team(r, "m")), "Strict")):
    lab = [(doc[r["item"]], (r["p_same"], lab_f(r))) for r in rated]
    a = auc([x for _, x in lab]); lo, hi = boot(lab, auc)
    npos = sum(y for _, (_, y) in lab)
    M[f"hAuc{key}"] = f"{a:.2f}"; M[f"hAuc{key}Lo"] = f"{lo:.2f}"; M[f"hAuc{key}Hi"] = f"{hi:.2f}"
    scorer_rows.append((name, npos, len(lab), a, lo, hi))
three = [r for r in rated if len(team(r, "m")) >= 3]
lab3 = [(doc[r["item"]], (r["p_same"], kept[r["task"]])) for r in three]
a3 = auc([x for _, x in lab3]); lo3, hi3 = boot(lab3, auc)
M["hAucThree"], M["hAucThreeLo"], M["hAucThreeHi"], M["hThreeN"] = f"{a3:.2f}", f"{lo3:.2f}", f"{hi3:.2f}", len(three)
evenr = [r for r in rated if r["stratum"] == "even"]
labe = [(doc[r["item"]], (r["p_same"], kept[r["task"]])) for r in evenr]
ae = auc([x for _, x in labe]); loe, hie = boot(labe, auc)
M["hAucEven"], M["hAucEvenLo"], M["hAucEvenHi"] = f"{ae:.2f}", f"{loe:.2f}", f"{hie:.2f}"

thr_rows = []
pos = [r for r in rated if kept[r["task"]]]; neg = [r for r in rated if not kept[r["task"]]]
for th in (0.3, 0.5, 0.7):
    caught = sum(r["p_same"] < th for r in neg); wrong = sum(r["p_same"] < th for r in pos)
    agree = sum((r["p_same"] >= th) == kept[r["task"]] for r in rated)
    thr_rows.append((th, caught, len(neg), wrong, len(pos), 100 * agree / len(rated)))
    if th == 0.5:
        M["hCaught"], M["hLosses"], M["hWrongFail"], M["hAgreeFive"] = caught, len(neg), wrong, f"{100 * agree / len(rated):.0f}"
M["hMissed"] = M["hLosses"] - M["hCaught"]
major = [r for r in rated if lost_major[r["task"]]]
M["hMajor"], M["hMajorCaught"] = len(major), sum(r["p_same"] < 0.5 for r in major)

# per system, even sample: humans and the scorer on the same outputs
sys_rows = []
for s, label in SYSTEMS.items():
    rs = [r for r in evenr if r["system"] == s]
    d = lambda f: [(doc[r["item"]], f(r)) for r in rs]
    hs = rate_ci(d(lambda r: kept[r["task"]]))
    gs = rate_ci(d(lambda r: r["p_same"] >= 0.5))
    ez = [r for r in rs if team(r, "e")]
    easier = rate_ci([(doc[r["item"]], maj(team(r, "e"), "easier")) for r in ez])
    arab = rate_ci([(doc[r["item"]], not maj(team(r, "a"), "major") and not maj(team(r, "a"), "minor")) for r in rs if team(r, "a")])
    sys_rows.append((label, len(rs), hs, gs, easier, arab))
    tag = s.replace("model2-", "M").replace("app-", "App").replace("-notag", "N").replace("arat5", "Tfive").replace("arabart", "Bart")
    M[f"h{tag}Same"] = f"{hs[0]:.0f}"; M[f"h{tag}Gemma"] = f"{gs[0]:.0f}"; M[f"h{tag}Easier"] = f"{easier[0]:.0f}"
M["hBartSameMin"] = f"{min(hs[0] for l, n, hs, gs, ez, ar in sys_rows if 'AraBART' in l):.0f}"
M["hBartSameMax"] = f"{max(hs[0] for l, n, hs, gs, ez, ar in sys_rows if 'AraBART' in l):.0f}"
M["hEasierMin"] = f"{min(ez[0] for l, n, hs, gs, ez, ar in sys_rows):.0f}"
M["hEasierMax"] = f"{max(ez[0] for l, n, hs, gs, ez, ar in sys_rows):.0f}"
M["hArabicMin"] = f"{min(ar[0] for l, n, hs, gs, ez, ar in sys_rows):.0f}"
M["hArabicMax"] = f"{max(ar[0] for l, n, hs, gs, ez, ar in sys_rows):.0f}"
gaps = [round(hs[0]) - round(gs[0]) for l, n, hs, gs, ez, ar in sys_rows]   # as the table prints them
M["hGapMin"], M["hGapMax"] = f"{min(gaps):.0f}", f"{max(gaps):.0f}"
t5 = [(hs[0], gs[0]) for l, n, hs, gs, ez, ar in sys_rows if "AraT5" in l]
bt = [(hs[0], gs[0]) for l, n, hs, gs, ez, ar in sys_rows if "AraBART" in l]
M["hOrderRaters"] = "yes" if min(h for h, g in t5) > max(h for h, g in bt) else "no"
M["hOrderScorer"] = "yes" if min(g for h, g in t5) > max(g for h, g in bt) else "no"
M["hPerSystem"] = len([r for r in evenr if r["system"] == "app-arat5"])

# the reader with dyslexia (ease only)
rd = [r for r in singles if "e" in r["ratings"].get(READER, {})]
rc = collections.Counter(r["ratings"][READER]["e"] for r in rd)
M["rN"], M["rEasier"], M["rSame"], M["rHarder"] = len(rd), rc["easier"], rc["same"], rc["harder"]
rsys = {s: collections.Counter(r["ratings"][READER]["e"] for r in rd if r["system"] == s) for s in SYSTEMS}
agree_r = [(r["ratings"][READER]["e"], collections.Counter(team(r, "e")).most_common(1)[0][0]) for r in rd if team(r, "e")]
M["rAgree"] = f"{100 * sum(a == b for a, b in agree_r) / len(agree_r):.0f}"; M["rAgreeN"] = len(agree_r)
rp = [r for r in pairs if "p" in r["ratings"].get(READER, {})]
M["rPairs"] = len(rp)

# pairwise comparisons, team raters: wins per contrast
cmp_rows = []
by = collections.defaultdict(collections.Counter)
for r in pairs:
    for n in TEAM:
        v = r["ratings"].get(n, {}).get("p")
        if v:
            who = {"a": r["a"], "b": r["b"], "same": "tie"}[v]
            by[(r["contrast"], *sorted((r["a"], r["b"])))][who] += 1
for (c, x, y), cnt in sorted(by.items()):
    cmp_rows.append((c, x, y, cnt[x], cnt["tie"], cnt[y]))

def fmt_ci(t, dec=0):
    m, lo, hi = t
    return r"\makecell{" + f"{m:.{dec}f}" + r"\\[-2pt]{\tiny[" + f"{lo:.0f}--{hi:.0f}" + "]}}"


out = ["% Generated by make_human.py -- do not edit by hand."]
out += [rf"\newcommand{{\{k}}}{{{v:,}}}" if isinstance(v, int) else rf"\newcommand{{\{k}}}{{{v}}}" for k, v in M.items()]

t = [r"\begin{table}[h]", r"\small",
     r"\caption{The open meaning scorer (Gemma~4 31B, P(same meaning)) against the human verdicts on the "
     rf"\hRated{{}} rated single outputs. AUC: the chance that an output the raters kept scores higher than one they "
     r"did not (0.5 = chance, 1 = perfect); 95\% intervals from a bootstrap over documents.}",
     r"\label{tab:scorerauc}", r"\begin{tabularx}{\linewidth}{|L|C{22mm}|C{28mm}|}", r"\hline",
     r"\head{Human verdict counted as ``meaning kept''} & \head{Kept} & \head{AUC [95\% CI]} \\ \hline"]
for name, npos, n, a, lo, hi in scorer_rows:
    t.append(f"{name[0].upper() + name[1:]} & {npos} of {n} & {a:.2f} [{lo:.2f}--{hi:.2f}]" + r" \\ \hline")
t.append(rf"Majority ``same meaning'', tasks with three or more raters & {sum(y for _, (_, y) in lab3)} of {len(lab3)} & "
         rf"{a3:.2f} [{lo3:.2f}--{hi3:.2f}] \\ \hline")
t.append(r"\multicolumn{3}{|l|}{\cellcolor{sichead}\textbf{The scorer as a pass/fail rule (kept = majority ``same meaning'')}} \\ \hline")
t.append(r"\head{Threshold on P(same)} & \head{Losses caught} & \head{Kept outputs failed} \\ \hline")
for th, c, nn, w, npos, ag in thr_rows:
    t.append(f"{th:.1f}{' (frozen)' if th == 0.5 else ''} & {c} of {nn} & {w} of {npos}" + r" \\ \hline")
t += [r"\end{tabularx}", r"\end{table}"]
out.append(r"\newcommand{\scoreraucatable}{" + "\n".join(t) + "}")

t = [r"\begin{table}[h]", r"\small",
     r"\caption{Each system as the raters and the scorer saw the same outputs: the "
     rf"\hPerSystem{{}} changed outputs per system drawn evenly (copies of the input were not rated). Rates in \%, a "
     r"strict majority of the task's raters; 95\% intervals from a bootstrap over documents. "
     r"\emph{Scorer}: P(same) $\geq$ 0.5 on the same outputs.}",
     r"\label{tab:humansys}", r"\begin{tabularx}{\linewidth}{|L|C{18mm}|C{18mm}|C{18mm}|C{18mm}|}", r"\hline",
     r"\head{System} & \head{Same meaning: raters} & \head{Same meaning: scorer} & \head{Easier: raters} & "
     r"\head{Correct Arabic: raters} \\ \hline"]
for label, n, hs, gs, ez, ar in sys_rows:
    t.append(f"{label} & {fmt_ci(hs)} & {fmt_ci(gs)} & {fmt_ci(ez)} & {fmt_ci(ar)}" + r" \\ \hline")
t += [r"\end{tabularx}", r"\end{table}"]
out.append(r"\newcommand{\humansystable}{" + "\n".join(t) + "}")

t = [r"\begin{table}[h]", r"\small",
     rf"\caption{{The reader with dyslexia: ``was it easier for you to read?'' on \rN{{}} outputs (five per system), "
     r"against the original.}", r"\label{tab:reader}",
     r"\begin{tabularx}{\linewidth}{|L|C{18mm}|C{18mm}|C{18mm}|}", r"\hline",
     r"\head{System} & \head{Easier} & \head{Same} & \head{Harder} \\ \hline"]
for s, label in SYSTEMS.items():
    c = rsys[s]
    t.append(f"{label} & {c['easier']} & {c['same']} & {c['harder']}" + r" \\ \hline")
t.append(rf"\textbf{{All}} & \textbf{{{rc['easier']}}} & \textbf{{{rc['same']}}} & \textbf{{{rc['harder']}}} \\ \hline")
t += [r"\end{tabularx}", r"\end{table}"]
out.append(r"\newcommand{\readertable}{" + "\n".join(t) + "}")

t = [r"\begin{table}[h]", r"\small",
     r"\caption{Side-by-side comparisons by the team raters: which version is better for a reader with dyslexia "
     r"(easier, with the same meaning). Counts of rater votes.}", r"\label{tab:pairs}",
     r"\begin{tabularx}{\linewidth}{|p{20mm}|L|C{10mm}|C{10mm}|C{10mm}|}", r"\hline",
     r"\head{Contrast} & \head{Systems (first vs second)} & \head{First} & \head{Tie} & \head{Second} \\ \hline"]
for c, x, y, wx, tie, wy in cmp_rows:
    t.append(f"{c} & {SYSTEMS[x]} vs {SYSTEMS[y]} & {wx} & {tie} & {wy}" + r" \\ \hline")
t += [r"\end{tabularx}", r"\end{table}"]
out.append(r"\newcommand{\pairstable}{" + "\n".join(t) + "}")

# figure data: ROC of P(same) against the majority verdict, and P(same) by the raters' majority answer
def roc(lab):
    pos = sum(1 for _, y in lab if y); neg = len(lab) - pos
    pts, seen = [(0.0, 0.0)], set()
    for th in sorted({p for p, _ in lab} | {1.01}, reverse=True):
        tpr = sum(p >= th for p, y in lab if y) / pos; fpr = sum(p >= th for p, y in lab if not y) / neg
        if (fpr, tpr) not in seen:
            seen.add((fpr, tpr)); pts.append((fpr, tpr))
    pts.append((1.0, 1.0))
    return " ".join(f"({x:.3f},{y:.3f})" for x, y in sorted(set(pts)))
labs = [(r["p_same"], kept[r["task"]]) for r in rated]
labnm = [(r["p_same"], not lost_major[r["task"]]) for r in rated]
out.append(r"\newcommand{\rocsame}{" + roc(labs) + "}")
out.append(r"\newcommand{\rocnotmajor}{" + roc(labnm) + "}")
mv = lambda r: ("same" if maj(team(r, "m"), "same") else "major" if maj(team(r, "m"), "major") else "minor")
rng = random.Random(7)
for v, name in (("same", "Same"), ("minor", "Minor"), ("major", "Major")):
    pts = [(r["p_same"], {"same": 3, "minor": 2, "major": 1}[v] + rng.uniform(-0.28, 0.28)) for r in rated if mv(r) == v]
    out.append(rf"\newcommand{{\strip{name}}}{{" + " ".join(f"({x:.3f},{y:.3f})" for x, y in pts) + "}")
    M[f"hVerdict{name}"] = len(pts)
out.append(rf"\newcommand{{\hVerdictSame}}{{{M['hVerdictSame']}}}\newcommand{{\hVerdictMinor}}{{{M['hVerdictMinor']}}}\newcommand{{\hVerdictMajor}}{{{M['hVerdictMajor']}}}")
# per system dumbbell: raters vs scorer, even sample
out.append(r"\newcommand{\dumbbell}{" + ",".join(f"{i}/{hs[0]:.1f}/{gs[0]:.1f}" for i, (label, n, hs, gs, ez, ar) in enumerate(sys_rows)) + "}")
Path("human.tex").write_text("\n".join(out) + "\n", encoding="utf-8")
json.dump({k: v for k, v in M.items()}, open("eval/human_summary.json", "w"), indent=1)
print(json.dumps(M, indent=0)[:3000])
print(scorer_rows, thr_rows, sys_rows, cmp_rows, sep="\n")
