"""SUBMISSION deck: PowerPoint-native. Every element is an editable shape or text box; animations are PowerPoint's own
entrance/exit effects, one click per step (same steps as the presenting deck). No video, no baked fonts.

    python build_native.py  -> ../Bayan_Submission.pptx  

Fonts used: Readex Pro (Latin), Noto Naskh Arabic and Amiri (Arabic). Install them on the machine that opens the deck.
"""
from pathlib import Path

from pptx import Presentation

from assemble_presenting import SLIDES, TEMPLATE
from script_data import slide_notes
from nativekit import *  # noqa: F401,F403

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUT = HERE.parent / "Bayan_Submission.pptx"
NOTES = {scene: slide_notes(scene) for scene, _, _ in SLIDES}
MX, CW = 0.65, SW - 1.3  # side margin, content width
TOTAL = 9


def chrome(c, num, kicker=None, title=None, dark=False):
    fg = CREAM if dark else INK
    if kicker:
        c.rect(MX, 0.55, 0.06, 0.24, SUN)
        c.text(MX + 0.16, 0.5, 5, 0.34, kicker.upper(), 11, SUN, True)
    if title:
        c.text(MX, 0.9, CW, 0.6, title, 28, fg, True)
    c.pic(ASSETS / ("samsung-white.png" if dark else "samsung-blue.png"), MX, 6.92, 1.15, "Samsung", "Samsung logo")
    c.text(MX + 1.35, 6.87, 4.5, 0.3, "Samsung Innovation Campus  ·  AI Course", 10, CREAM if dark else INK3)
    c.text(SW - MX - 1.0, 6.87, 1.0, 0.3, f"{num} / {TOTAL}", 10, CREAM if dark else INK3, align="r")


def chip(c, x, y, text, size=12, fill=SUN_LT, color=SUN_DK, h=0.36, w=None, bold=True):
    w = w or (0.28 + 0.088 * size * len(text) / 1.25 * 0.72)
    return c.card(x, y, w, h, fill=fill, line=None, radius=0.18, text=text, size=size, color=color, bold=bold)


# ------------------------------------------------------------------------------------------------ 1
def s1(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 1, dark=True)
    logo = c.pic(ASSETS / "bayan-mark-dark.png", (SW - 3.3) / 2, 0.95, 3.3, "Bayan logo: open book with a sun", "Bayan logo")
    title = c.text(0, 3.25, SW, 0.9, "Bayan", 54, CREAM, True, "c")
    sub = c.text(0, 4.2, SW, 0.4, "On-device Arabic text simplification for readers with dyslexia", 18, CREAM, align="c")
    team = c.text(0, 4.9, SW, 0.35, "Team Cogni", 16, SUN, True, "c")
    names = c.text(0, 5.35, SW, 0.3, "Marwan Elamami  ·  Abdulrahman Khengari  ·  Ahmed Alaeb  ·  Sanad Ali  ·  "
                   "Mohammed Thabet  ·  Abdul Majid Mraied", 10.5, INK4, align="c")
    c.step((logo, "wipe_left", 0, 1500), (title, "fade", 1300), (sub, "fade", 1700), (team, "fade", 2100),
           (names, "fade", 2100), auto=True)
    c.finish(NOTES["S1Cover"])


# ------------------------------------------------------------------------------------------------ 2
def s2(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 2, "01 · The idea", "Arabic hides its own pronunciation")
    pct = c.text(0.65, 2.15, 3.7, 1.3, "11%", 84, SUN, False, "c")
    lab = c.text(0.65, 3.55, 3.7, 0.7, "of Arab primary-school children\nhave developmental dyslexia", 16, INK2, align="c")
    src = c.text(0.65, 4.3, 3.7, 0.3, "pooled over 18 studies, N = 30,243", 11.5, INK3, align="c")
    c.step((pct, "fade"), (lab, "fade", 300), (src, "fade", 500), auto=True)

    panel = c.card(4.7, 1.8, 5.48, 3.55)
    word = c.text(4.7, 1.95, 5.48, 1.2, "كتب", 72, INK, False, "c", ARABIC_DISPLAY)
    cap = c.text(4.7, 3.15, 5.48, 0.28, "one written form", 12, INK3, align="c")
    cols = [(9.35, "كَتَبَ", "kataba", "he wrote"), (7.44, "كُتِبَ", "kutiba", "it was written"), (5.53, "كُتُب", "kutub", "books")]
    arrows, reads = [], []
    for x, ar, tr, en in cols:
        arrows.append(c.line(7.44, 3.5, x, 3.85, SUN, 2, arrow=True))
        reads.append(c.text(x - 0.9, 3.85, 1.8, 0.75, ar, 36, INK, False, "c", ARABIC_DISPLAY))
        reads.append(c.text(x - 0.9, 4.65, 1.8, 0.55, [(tr, 12, SUN_DK, True, LATIN), (en, 11.5, SUN_DK, False, LATIN)], 12, align="c"))
    c.step((panel, "fade"), (word, "fade", 150), (cap, "fade", 400),
           *[(a, "fade", 700 + 250 * i) for i, a in enumerate(arrows)],
           *[(r, "fade", 800 + 250 * (i // 2)) for i, r in enumerate(reads)])

    c1 = c.card(MX, 5.62, 8.6, 0.46, PAPER2, PAPER3, 0.23, "Fused prefixes and suffixes  →  long words that resist chunking", 13, INK2, align="l")
    c2 = c.card(MX, 6.18, 8.6, 0.46, PAPER2, PAPER3, 0.23, "Clauses chained with و and ف  →  sentences longer than working memory", 13, INK2, align="l")
    c.step((c1, "fade"), (c2, "fade", 350))
    c.finish(NOTES["S2Problem"])


# ------------------------------------------------------------------------------------------------ 3
def s3(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "01 · The idea", "Nobody had built this: no tool, no data")
    xs = [4.55, 6.2, 7.85, 9.5]
    heads, subs = [], []
    for x, n, s in zip(xs, ["SAMER", "BAREC", "Baseet", "DAASI"],
                       ["15 novels,\n3 levels", "69,441\nsentences", "3 LLM\nlevels", "government &\ninsurance text"]):
        heads.append(c.text(x - 0.8, 1.85, 1.6, 0.35, n, 16, INK, True, "c"))
        subs.append(c.text(x - 0.8, 2.2, 1.6, 0.45, s, 10.5, INK3, align="c", line_spacing=0.9))
    rule = c.line(MX, 2.8, SW - MX, 2.8, PAPER3, 2)
    rows = [("Rewrites by", ["human", "levels only", "LLM", "human-verified"]),
            ("Adds a sentence", ["0% of pairs", "n/a", "2–4%", "8%"]),
            ("Made for dyslexia", ["no", "no", "no", "no"])]
    ys = [3.35, 4.1, 4.85]
    band = c.card(MX - 0.1, ys[2] - 0.34, CW + 0.2, 0.68, WARN_LT, WARN_LT, 0.15)
    items = []
    for r, ((name, vals), y) in enumerate(zip(rows, ys)):
        last = r == 2
        lab = c.text(MX, y - 0.2, 3.0, 0.4, name, 15, WARN if last else INK2, last)
        cells = [c.text(x - 0.8, y - 0.2, 1.6, 0.4, v, 14, WARN if last else INK2, last, "c") for x, v in zip(xs, vals)]
        items.append([lab] + cells)
    c.step(*[(s, "fade", 100 * i) for i, s in enumerate(heads + subs)], (rule, "fade", 300),
           *[(s, "fade", 500 + 300 * r) for r in (0, 1) for s in items[r]], auto=True)
    c.step((band, "fade"), *[(s, "fade", 150) for s in items[2]])
    gap = c.text(MX, 5.65, CW, 0.35, "No deployed Arabic dyslexia tool simplifies text, and no open corpus teaches splitting.", 14, INK2, align="c")
    dot = c.circle(1.25, 6.28, 0.09, SUN)
    plan = c.text(1.5, 6.08, SW - 2.2, 0.4, "So we built our own data, our own models and our own benchmark.", 16, INK, True)
    c.step((gap, "fade"), (dot, "fade", 400), (plan, "fade", 400))
    c.finish(NOTES["S3Gap"])


# ------------------------------------------------------------------------------------------------ 4
def s4(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "02 · The verdict", "Simplify where the reader already is")
    q = c.text(MX, 1.6, 6.3, 0.35, "Where does a reader meet hard Arabic?  Inside other apps.", 14, INK2)
    opts = []
    for i, (tag, name, why) in enumerate([("A", "Chrome extension", "desktop-first; reading happens on the phone"),
                                          ("B", "Android plugin", "«تبسيط» in the selection menu of every app"),
                                          ("C", "Standalone app", "copy, paste, leave the app: the friction we remove")]):
        y = 2.15 + i * 1.12
        box = c.card(MX, y, 5.95, 0.95)
        badge = c.circle(MX + 0.5, y + 0.475, 0.26, SUN if tag == "B" else INK4)
        c.text(0, 0, 0, 0, tag, 15, PAPER, True, "c", shape=badge)
        txt = c.text(MX + 0.95, y + 0.1, 4.9, 0.75, [(name, 16, INK, True, LATIN), (why, 12, INK3, False, LATIN)], 12)
        opts.append((box, badge, txt))
    c.step((q, "fade"), *[(s, "fade", 200 * i) for i, o in enumerate(opts) for s in o], auto=True)

    ph = c.rect(7.45, 1.7, 2.7, 4.85, PAPER, INK, 3, 0.3)
    widths = [2.0, 2.2, 1.9, 2.2, 1.5, 2.2, 2.0]
    lines = [c.rect(9.95 - w, 2.05 + i * 0.3, w, 0.11, PAPER3, radius=0.05) for i, w in enumerate(widths)]
    sel = [c.rect(9.95 - widths[i], 2.02 + i * 0.3, widths[i], 0.17, SUN, radius=0.06, alpha=0.55) for i in (2, 3, 4)]
    menu = c.card(7.6, 2.5, 2.4, 0.5, "FFFFFF", PAPER3, 0.14)
    m1 = c.text(7.7, 2.5, 0.6, 0.5, "Copy", 11, INK3, align="c")
    m2 = c.text(8.35, 2.5, 0.75, 0.5, "تبسيط", 17, SUN_DK, True, "c", ARABIC)
    m3 = c.text(9.15, 2.5, 0.75, 0.5, "Share", 11, INK3, align="c")
    sheet = c.card(7.6, 4.3, 2.4, 2.1, PAPER2, INK4, 0.22)
    handle = c.rect(8.55, 4.4, 0.5, 0.07, INK4, radius=0.03)
    outs = [c.rect(9.75 - w, 4.65 + i * 0.28, w, 0.12, SUN, radius=0.05) for i, w in enumerate([1.95, 1.65, 1.85])]
    play = c.circle(7.95, 5.95, 0.2, SUN)
    tri = c.rect(7.9, 5.88, 0.12, 0.14, PAPER)
    tri.auto_shape_type  # (a plain square stands in for the triangle; replaced below)
    c.sh._spTree.remove(tri._element)
    tri = c.sh.add_shape(MSO_SHAPE.ISOSCELES_TRIANGLE, Inches(7.89), Inches(5.87), Inches(0.14), Inches(0.16))
    tri.rotation = 90
    c._style(tri, PAPER)
    menu_grp = [menu, m1, m2, m3]
    sheet_grp = [sheet, handle, *outs, play, tri]
    c.step((ph, "fade"), *[(l, "fade", 200) for l in lines],
           *[(s, "wipe_left", 900 + 250 * i, 600) for i, s in enumerate(sel)],
           *[(s, "fade", 1900) for s in menu_grp],
           *[(s, "fade_out", 3400) for s in menu_grp],
           *[(s, "wipe_up", 3500, 800) for s in sheet_grp])
    dim_a = c.card(MX - 0.05, 2.1, 6.05, 1.05, PAPER, None, 0.16, alpha=0.7)
    dim_c = c.card(MX - 0.05, 4.34, 6.05, 1.05, PAPER, None, 0.16, alpha=0.7)
    ring = c.rect(MX, 3.27, 5.95, 0.95, None, SUN, 3.5, 0.16)
    r1 = [chip(c, MX + 0.15 + k * w, 5.72, t, 12, w=w - 0.1) for k, (t, w) in
          enumerate([("on-device", 1.35), ("offline", 1.15), ("≤ 250 MB", 1.35)])]
    r1[1].left = Inches(MX + 0.15 + 1.35)
    r1[2].left = Inches(MX + 0.15 + 1.35 + 1.15)
    r2 = chip(c, MX + 0.15, 6.2, "the reader’s text never leaves the phone", 12, w=4.2)
    c.step((dim_a, "fade"), (dim_c, "fade"), (ring, "fade", 300), *[(s, "fade", 700 + 150 * i) for i, s in enumerate(r1 + [r2])])
    c.finish(NOTES["S4Verdict"])


# ------------------------------------------------------------------------------------------------ 5
def s5(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "03 · Data", "Audit first, then build the training set")
    big = c.text(MX, 1.75, 2.9, 1.1, "9.3%", 60, WARN, True, "c")
    txt = c.text(3.75, 1.85, 6.4, 0.9, "of Baseet overlapped our locked test sets.\nEvery training file now passes a leakage gate.", 17, INK2)
    c.step((big, "fade"), (txt, "fade", 400), auto=True)

    title = c.text(MX, 3.05, CW, 0.35, "22,733 training pairs, every one tagged with its source style", 15, INK, True)
    total = 22733
    segs = [("[S0]", "14,343", "SAMER · 6,033 unchanged kept", INK, CREAM), ("[S1]", "3,508", "Baseet · light", SUN_DK, CREAM),
            ("[S2]", "1,954", "Baseet · medium", SUN, INK), ("[S3]", "1,426", "Baseet · strong", "DDBB95", INK),
            ("[SA]", "1,502", "DAASI · everyday", INK3, CREAM)]
    x, bars, legend = MX, [], []
    colw = CW / 5
    for i, (tag, n, note, col, fg) in enumerate(segs):
        w = CW * int(n.replace(",", "")) / total
        b = c.card(x, 3.55, w, 0.75, col, PAPER, 0.0, text=tag, size=14 if w > 0.7 else 11, color=fg, bold=True)
        bars.append(b)
        x += w
        sw = c.rect(MX + colw * i, 4.62, 0.16, 0.16, col)
        num = c.text(MX + colw * i + 0.24, 4.52, 1.4, 0.36, n, 17, INK, True)
        nt = c.text(MX + colw * i, 4.9, colw - 0.1, 0.45, note, 11, INK3, anchor="t")
        legend += [sw, num, nt]
    c.step((title, "fade"), *[(b, "wipe_left", 250 * i, 700) for i, b in enumerate(bars)],
           *[(s, "fade", 1300 + 90 * i) for i, s in enumerate(legend)])
    dot = c.circle(0.85, 6.02, 0.08, SUN)
    gate = c.text(1.05, 5.82, SW - 1.7, 0.4, "Baseet pairs pass a meaning filter:  LaBSE ≥ 0.646  ·  length ≥ 67% of source  ·  every number kept",
                  13, INK2)
    gate2 = c.text(1.05, 6.2, SW - 1.7, 0.3, "each threshold = 5th percentile of human-verified rewrites (DAASI)", 11, INK3)
    c.step((dot, "fade"), (gate, "fade", 200), (gate2, "fade", 500))
    c.finish(NOTES["S5Data"])


# ------------------------------------------------------------------------------------------------ 6
def s6(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "04 · Training", "Two candidates, one recipe")
    card = c.card(MX, 1.75, CW, 1.25)
    head = c.text(MX, 1.83, CW, 0.4, "one script (train.py)  ·  identical data  ·  architecture is the only difference", 15, INK, True, "c")
    labels = ["10 epochs", "fp16", "seed 42", "max length 256", "best SARI on changed rows"]
    widths = [1.15, 0.85, 0.95, 1.55, 2.75]
    x = MX + (CW - sum(widths) - 0.15 * 4) / 2
    chips = []
    for t, w in zip(labels, widths):
        chips.append(chip(c, x, 2.4, t, 11, PAPER, INK2, 0.34, w, False))
        x += w + 0.15
    c.step((card, "fade"), (head, "fade", 200), *[(s, "fade", 400 + 120 * i) for i, s in enumerate(chips)], auto=True)

    specs = [("AraT5v2", 368, INK, "368M params  ·  won Baseet’s head-to-head  ·  models 1 & 2", False),
             ("AraBART", 139, SUN, "139M params  ·  2.6× smaller  ·  the on-device contender", False),
             ("HPLT T5", 294, INK4, "≈ 294M params  ·  held in reserve", True)]
    eff = []
    for i, (name, m, col, note, dashed) in enumerate(specs):
        y = 3.4 + i * 1.02
        n = c.text(MX, y, 1.6, 0.45, name, 16, INK, True)
        w = 5.6 * m / 368
        r = c.rect(2.3, y, w, 0.45, col if not dashed else PAPER3, line=col, line_w=2.5)
        nt = c.text(2.3, y + 0.5, 7.5, 0.3, note, 12, INK3)
        eff += [(n, "fade", 600 * i), (r, "wipe_left", 600 * i, 700), (nt, "fade", 600 * i + 500)]
    c.step(*eff)
    dot = c.circle(0.85, 6.55, 0.08, SUN)
    tail = c.text(1.05, 6.35, SW - 1.7, 0.4, "46% of AraT5v2 is two embedding tables, so shrinking its vocabulary is the route to phone size.", 13, INK2)
    c.step((dot, "fade"), (tail, "fade", 300))
    c.finish(NOTES["S6Candidates"])


# ------------------------------------------------------------------------------------------------ 7
def s7(prs, layout):
    """Two charts side by side (not one chart that flips): reads correctly even where animations are ignored."""
    c = Canvas(prs, layout, PAPER)
    chrome(c, 7, "04 · Training", "Model 1: the score that looked like a failure")
    base_y, hmax = 4.95, 2.35

    def chart(x0, head, sub, vals, verdict, vcol, why):
        shapes = [c.text(x0, 1.65, 4.6, 0.36, head, 15, INK, True), c.text(x0, 2.02, 4.6, 0.3, sub, 11, INK3)]
        axis = c.line(x0, base_y, x0 + 4.5, base_y, INK4, 2.5)
        bars = []
        for i, (lab, v, col) in enumerate(vals):
            h = hmax * v / 100
            cx = x0 + 1.15 + i * 2.15
            b = c.rect(cx - 0.6, base_y - h, 1.2, h, col)
            val = c.text(cx - 0.6, base_y - h - 0.4, 1.2, 0.36, f"{v:.2f}", 16, INK, True, "c")
            cat = c.text(cx - 1.0, base_y + 0.08, 2.0, 0.3, lab, 12.5, INK2, align="c")
            bars += [b, val, cat]
        ver = c.text(x0, 5.5, 4.6, 0.4, verdict, 19, vcol, True)
        wh = c.text(x0, 5.92, 4.6, 0.55, why, 12.5, INK2, anchor="t")
        return shapes + [axis], bars, [ver, wh]

    c.line(5.4, 1.7, 5.4, 6.4, PAPER3, 2)
    h1, b1, v1 = chart(MX, "SARI on all SAMER test rows", "3,277 sentences, half need no change",
                       [("copy the input", 77.50, INK4), ("Model 1", 75.88, SUN)], "Copying wins?", WARN,
                       "Half of SAMER needs no change,\nso doing nothing scores well.")
    h2, b2, v2 = chart(5.75, "SARI on rows a human changed", "1,678 sentences: the bar a model must clear",
                       [("copy the input", 56.06, INK4), ("Model 1", 61.83, SUN)], "Model 1 clears it", SUN_DK,
                       "+5.8 points, greedy decoding:\nwhat the phone runs.")
    c.step(*[(s, "fade") for s in h1], *[(s, "wipe_up", 300, 900) for s in b1], *[(s, "fade", 1300) for s in v1], auto=True)
    note = c.text(MX, 6.45, CW, 0.32, "But it made mostly one-word edits, and 42% of its training pairs were unchanged sentences.", 12, INK3, align="c")
    c.step(*[(s, "fade") for s in h2], *[(s, "wipe_up", 300, 900) for s in b2], *[(s, "fade", 1300) for s in v2], (note, "fade", 1900))
    c.finish(NOTES["S7Model1"])


# ------------------------------------------------------------------------------------------------ 8
def s8(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 8, "04 · Training", "Model 2: one fix for each lesson")
    items = [("It rewards doing nothing", "Keep all 6,033 unchanged pairs;\npick the checkpoint on changed rows only"),
             ("SAMER is novels: it teaches word swaps", "Add DAASI (everyday, admin) and Baseet\n(educational) through a meaning filter"),
             ("One strength fits no one", "A strength tag on every source;\nat run time it is the app’s strength setting")]
    for i, (prob, fix) in enumerate(items):
        y = 1.8 + i * 1.22
        p = c.card(MX, y, 3.35, 1.0, WARN_LT, WARN_LT, 0.16, prob, 15, WARN, True)
        ar = c.line(4.1, y + 0.5, 4.75, y + 0.5, SUN, 3, arrow=True)
        f = c.card(4.9, y, SW - MX - 4.9, 1.0, PAPER2, PAPER3, 0.16, fix, 13.5, INK2)
        c.step((p, "fade"), (ar, "wipe_left", 350, 500), (f, "fade", 600), auto=(i == 0))
    tags = [("[S0]", "minimal"), ("[S1]", "light"), ("[S2]", "medium · default"), ("[S3]", "strong"), ("[SA]", "everyday")]
    tw, gap = 1.78, 0.1575
    cards = []
    for i, (t, m) in enumerate(tags):
        cards.append(c.card(MX + i * (tw + gap), 5.65, tw, 0.95, PAPER, SUN, 0.15,
                            [(t, 18, INK, True, LATIN), (m, 11, INK3, False, LATIN)], 12))
    dot = c.circle(MX + 2 * (tw + gap) + tw / 2, 5.5, 0.09, SUN)
    c.step(*[(s, "fade", 200 * i) for i, s in enumerate(cards)], (dot, "fade", 1300))
    c.finish(NOTES["S8Model2"])


# ------------------------------------------------------------------------------------------------ 9
def s9(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 9, dark=True)
    logo = c.pic(ASSETS / "bayan-horizontal-dark.png", (SW - 3.9) / 2, 1.25, 3.9, "Bayan logo", "Bayan logo")
    line = c.text(0, 3.2, SW, 0.7, "Simplify where you read.", 34, CREAM, True, "c")
    c.step((logo, "fade"), (line, "fade", 500), auto=True)
    nxt = c.text(0, 4.35, SW, 0.4, "Next: does it work?", 18, SUN, True, "c")
    labels = ["BayanBench: a benchmark for the reader’s task", "On a real phone", "Readers with dyslexia"]
    widths = [4.75, 1.75, 2.15]
    x = (SW - sum(widths) - 0.3) / 2
    chips = []
    for t, w in zip(labels, widths):
        chips.append(chip(c, x, 5.0, t, 12.5, NIGHT2, CREAM, 0.42, w, False))
        x += w + 0.15
    slogan = c.pic(ASSETS / "sic-slogan-white.png", (SW - 1.9) / 2, 5.85, 1.9, "Samsung Innovation Campus slogan", "SIC slogan")
    c.step((nxt, "fade"), *[(s, "fade", 300 + 200 * i) for i, s in enumerate(chips)], (slogan, "fade", 1100))
    c.finish(NOTES["S9Close"])


def main():
    prs = Presentation(TEMPLATE)
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    layout = next(l for l in prs.slide_layouts if l.name == "Body")
    for build in (s1, s2, s3, s4, s5, s6, s7, s8, s9):
        build(prs, layout)
    prs.save(OUT)
    print(f"{OUT.name}: {len(prs.slides)} slides, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
