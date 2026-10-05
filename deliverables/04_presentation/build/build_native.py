"""SUBMISSION deck: PowerPoint-native. Every element is an editable shape or text box; animations are PowerPoint's own
entrance/exit effects. Eight scenes matching the presenting deck's beats.

    python build_native.py  -> ../Bayan_Submission.pptx

Fonts: Readex Pro (Latin), Noto Naskh Arabic and Amiri (Arabic). Install them before opening.
Every number comes from facts.py; check_numbers.py must pass first.
"""
from pathlib import Path

from pptx import Presentation

from facts import FIG, SCATTER
from script_data import slide_notes
from nativekit import *  # noqa: F401,F403

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
OUT = HERE.parent / "Bayan_Submission.pptx"
TEMPLATE = next(HERE.parent.glob("SIC_AI_Capstone*Template.pptx"))
MX, CW = 0.65, SW - 1.3
TOTAL = 8


def F(key):
    return FIG[key][0]


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


# ---- 1 · Cover ---------------------------------------------------------------
def s1(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 1, dark=True)
    logo = c.pic(ASSETS / "bayan-mark-dark.png", (SW - 3.3) / 2, 0.95, 3.3, "Bayan logo: open book with a sun", "Bayan logo")
    title = c.text(0, 3.25, SW, 0.9, "Bayan", 54, CREAM, True, "c")
    sub = c.text(0, 4.2, SW, 0.4, "Simplify Arabic where you read", 18, CREAM, align="c")
    tag = c.text(0, 4.65, SW, 0.35, "on the phone, offline", 14, SUN, align="c")
    team = c.text(0, 5.2, SW, 0.35, "Team Cogni", 16, SUN, True, "c")
    names = c.text(0, 5.65, SW, 0.3, "Marwan Elamami  ·  Abdulrahman Khengari  ·  Ahmed Alaeb  ·  Sanad Ali  ·  "
                   "Mohammed Thabet  ·  Abdul Majid Mraied", 10.5, INK4, align="c")
    c.step((logo, "wipe_left", 0, 1500), (title, "fade", 1300), (sub, "fade", 1700), (tag, "fade", 1900),
           (team, "fade", 2100), (names, "fade", 2100), auto=True)
    c.finish(slide_notes("S1Cover"))


# ---- 2 · Problem + product ---------------------------------------------------
def s2(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 2, "01 · The problem", "Reading in Arabic adds load")
    pct = c.text(0.65, 1.85, 3.7, 1.2, f"{F('dyslexia_pct')}%", 80, SUN, False, "c")
    lab = c.text(0.65, 3.15, 3.7, 0.7, "of Arab primary-school children\nhave developmental dyslexia", 15, INK2, align="c")
    src = c.text(0.65, 3.9, 3.7, 0.3, "Al-Dakhil 2024, meta-analysis", 11, INK3, align="c")
    c.step((pct, "fade"), (lab, "fade", 300), (src, "fade", 500), auto=True)

    panel = c.card(4.7, 1.6, 5.48, 3.7)
    word = c.text(4.7, 1.75, 5.48, 1.1, "كتب", 68, INK, False, "c", ARABIC_DISPLAY)
    cap = c.text(4.7, 2.85, 5.48, 0.28, "one written form", 12, INK3, align="c")
    cols = [(9.35, "كَتَبَ", "kataba", "he wrote"), (7.44, "كُتِبَ", "kutiba", "it was written"), (5.53, "كُتُب", "kutub", "books")]
    arrows, reads = [], []
    for x, ar, tr, en in cols:
        arrows.append(c.line(7.44, 3.25, x, 3.6, SUN, 2, arrow=True))
        reads.append(c.text(x - 0.9, 3.6, 1.8, 0.7, ar, 32, INK, False, "c", ARABIC_DISPLAY))
        reads.append(c.text(x - 0.9, 4.35, 1.8, 0.55, [(tr, 12, SUN_DK, True, LATIN), (en, 11, SUN_DK, False, LATIN)], 12, align="c"))
    c.step((panel, "fade"), (word, "fade", 150), (cap, "fade", 400),
           *[(a, "fade", 700 + 250 * i) for i, a in enumerate(arrows)],
           *[(r, "fade", 800 + 250 * (i // 2)) for i, r in enumerate(reads)])

    phone = c.rect(1.0, 4.55, 1.55, 2.55, PAPER, INK, 2.5, 0.22)
    scr = c.rect(1.15, 4.7, 1.25, 2.25, PAPER2, radius=0.1)
    sel = c.rect(1.3, 5.15, 0.95, 0.22, SUN, radius=0.06, alpha=0.55)
    menu = c.card(1.25, 5.5, 1.15, 0.35, SUN, SUN, 0.12, "تبسيط", 13, NIGHT, True, "c")
    sheet = c.card(1.25, 6.05, 1.15, 0.7, PAPER2, SUN, 0.12)
    steps = c.card(3.0, 4.75, 5.2, 1.85)
    s1t = c.text(3.15, 4.85, 4.9, 0.35, "1  Select the hard text in any app", 13, INK2)
    s2t = c.text(3.15, 5.3, 4.9, 0.35, "2  Tap تبسيط in the menu", 13, SUN_DK, True)
    s3t = c.text(3.15, 5.75, 4.9, 0.55, "3  A sheet shows the simpler text\n     and reads it aloud", 13, INK2)
    c.step((phone, "fade"), (scr, "fade", 200), (sel, "fade", 500), (menu, "fade", 800),
           (sheet, "fade", 1100), (steps, "fade", 1400), (s1t, "fade", 1600), (s2t, "fade", 1800), (s3t, "fade", 2000))

    scope = chip(c, MX, 6.55, "We reduce load: long clauses, hard words.  Not decoding.", 12, SUN_LT, SUN_DK, 0.38, 6.5)
    c.step((scope, "fade"))
    c.finish(slide_notes("S2Problem"))


# ---- 3 · Data processing -----------------------------------------------------
def s3(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data processing", "Corpus v1, built behind gates")

    head = c.text(MX, 1.55, CW, 0.35, "What the first synthetic corpus got wrong", 16, INK, True)
    defects = [
        chip(c, MX, 2.05, f"{F('v0_tashkeel')}% of rows had tashkeel we strip anyway", 12, WARN_LT, WARN, 0.36, 4.8),
        chip(c, MX, 2.5, f"{F('v0_completed')}% of cut-off sources were simply completed", 12, WARN_LT, WARN, 0.36, 4.8),
        chip(c, MX, 2.95, f"{F('v0_short_rewritten')}% of short sources were rewritten", 12, WARN_LT, WARN, 0.36, 4.8),
        chip(c, MX, 3.4, f"only {F('v0_levels')}% of pairs were 2+ levels easier", 12, WARN_LT, WARN, 0.36, 4.8),
    ]
    why = c.text(MX, 3.95, CW, 0.3, "So every gate in corpus v1 exists because of a failure we saw.", 13, INK2)
    c.step((head, "fade"), *[(d, "fade", 200 + 150 * i) for i, d in enumerate(defects)], (why, "fade", 900), auto=True)

    # pipeline: source -> generation -> gates -> total
    stages = [
        ("BAREC train + dev", "test never enters", None),
        ("strip tashkeel / tatweel", "every text", None),
        ("route each source", "protected · short · hard", f"{F('route_hard'):,} hard"),
        ("Gemma 4 31B writes candidates", "hard band only", f"{F('gen_responses'):,} responses"),
        ("code gates", "numbers · quotes · options", None),
        ("readability + meaning gates", f"≥ 2 CAMeL levels · Qwen ≥ {F('meaning_gate')}", f"{F('accepted_tier_a'):,} accepted"),
    ]
    x0, y0, sw, sh, gap = MX, 4.55, 1.55, 0.85, 0.12
    cards, arrows = [], []
    for i, (title, sub, count) in enumerate(stages):
        x = x0 + i * (sw + gap)
        box = c.card(x, y0, sw, sh, PAPER2, PAPER3, 0.1)
        t = c.text(x + 0.05, y0 + 0.05, sw - 0.1, 0.35, title, 10, INK, True, "c")
        s = c.text(x + 0.05, y0 + 0.4, sw - 0.1, 0.35, sub, 8.5, INK3, align="c")
        cards += [box, t, s]
        if count:
            cards.append(c.text(x, y0 + sh + 0.08, sw, 0.25, count, 9.5, SUN_DK, True, "c"))
        if i > 0:
            arrows.append(c.line(x - gap, y0 + sh / 2, x, y0 + sh / 2, SUN, 1.5, arrow=True))
    c.step(*[(s, "fade", 200 * i) for i, s in enumerate(cards)], *[(a, "fade", 1200) for a in arrows])

    box = c.card(MX, 5.85, CW, 0.7, SUN_LT, SUN, 0.15)
    big = c.text(MX, 5.9, CW, 0.35, f"{F('corpus_rows'):,} rows  ·  0 rule violations  ·  0 leakage vs BAREC test", 15, SUN_DK, True, "c")
    audit = c.text(MX, 6.3, CW, 0.25, f"blind audit of {F('audit_n'):,} pairs: {F('audit_changed')}% meaning changed", 11, INK2, align="c")
    c.step((box, "fade"), (big, "fade", 300), (audit, "fade", 600))
    c.finish(slide_notes("S3Data"))


# ---- 4 · Training evolution --------------------------------------------------
def s4(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "03 · Training", "Each model answered the last failure")

    models = [
        ("Model 1", "AraT5v2 on SAMER", "SAMER L5→L3,\n14,343 pairs",
         "Copying scored higher.\nSwapped words, never restructured.", False),
        ("Model 2", "AraT5v2 and AraBART", "SAMER + DAASI +\nmeaning-filtered external",
         f"Meaning kept only {F('m2_meaning_tagged')}\nand {F('m2_meaning_arabart')}.", False),
        ("Model 3", "AraT5v2 on corpus v1", f"corpus v1, {F('corpus_rows'):,} rows,\n+ code safety net",
         "Every number kept.\nEasy text 74% vs 48%.", True),
    ]
    cw2 = 3.05
    gap2 = 0.35
    x_start = MX + (CW - 3 * cw2 - 2 * gap2) / 2
    cols, arrows = [], []
    for i, (name, what, data, found, highlight) in enumerate(models):
        x = x_start + i * (cw2 + gap2)
        lbl = c.text(x, 1.55, cw2, 0.25, what, 10, INK3, align="c")
        head = c.card(x, 1.85, cw2, 0.55, SUN if highlight else PAPER3, SUN if highlight else PAPER3, 0.12,
                      name, 15, NIGHT if highlight else INK, True, "c")
        d = c.card(x, 2.55, cw2, 1.1)
        dt = c.text(x + 0.08, 2.6, cw2 - 0.16, 1.0, data, 11, INK2, align="c")
        f = c.card(x, 3.8, cw2, 1.1, WARN_LT, WARN_LT, 0.12)
        ft = c.text(x + 0.08, 3.85, cw2 - 0.16, 1.0, found, 11, WARN, align="c")
        cols += [lbl, head, d, dt, f, ft]
        if i > 0:
            arrows.append(c.line(x - gap2 + 0.05, 3.1, x - 0.05, 3.1, SUN, 2.5, arrow=True))

    # step 1: model 1
    c.step(*[(s, "fade") for s in cols[0:6]], auto=True)
    # step 2: arrow + model 2
    c.step((arrows[0], "wipe_left", 0, 500), *[(s, "fade", 400) for s in cols[6:12]])
    # step 3: arrow + model 3
    c.step((arrows[1], "wipe_left", 0, 500), *[(s, "fade", 400) for s in cols[12:18]])

    # step 4: dropped branches
    dropped = chip(c, MX, 5.35, "Tried and dropped: MRT  ·  Gemma E2B teacher  ·  student DPO", 11, PAPER2, INK3, 0.36, 5.5)
    note = c.text(MX + 5.8, 5.35, 3.5, 0.36, "DPO learned the judge's preferences,\nnot meaning safety.", 10, INK3, anchor="m")
    c.step((dropped, "fade"), (note, "fade", 300))
    c.finish(slide_notes("S4Models"))


# ---- 5 · Measuring -----------------------------------------------------------
def s5(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")

    q = c.text(MX, 1.55, CW, 0.35, "Copying is the baseline to beat", 18, INK, True)
    rows = [
        ("Copy the input", 100, 0.0, True),
        ("v0.1", F("bt_m1_kept"), F("bt_m1_clause"), False),
        ("v0.2 (AraT5v2)", F("t5_untag_kept"), F("t5_untag_clause"), False),
        ("v0.2-Fast (AraBART)", F("bart_untag_kept"), F("bart_untag_clause"), False),
        ("v0.3", F("bt_m3_kept"), F("bt_m3_clause"), False),
    ]
    y0 = 2.05
    table, hdr = [], []
    hdr.append(c.text(MX + 3.4, y0 - 0.32, 1.3, 0.28, "meaning kept", 10, INK3, align="c"))
    hdr.append(c.text(MX + 4.85, y0 - 0.32, 1.7, 0.28, "words cut from\nlongest clause", 10, INK3, align="c", line_spacing=0.9))
    for i, (name, kept, cut, base) in enumerate(rows):
        y = y0 + i * 0.42
        band = c.card(MX, y, 6.7, 0.36, SUN_LT if base else PAPER2, SUN_LT if base else PAPER3, 0.1)
        n = c.text(MX + 0.15, y + 0.04, 3.1, 0.28, name, 12, INK, base or name == "v0.3")
        k = c.text(MX + 3.4, y + 0.04, 1.3, 0.28, f"{kept:.0f}%", 12, SUN_DK, True, "c")
        cutlab = "0" if cut < 0.05 else f"{cut:.1f}"
        u = c.text(MX + 4.85, y + 0.04, 1.7, 0.28, cutlab, 12, SUN_DK if cut >= 0.05 else WARN, True, "c")
        table += [band, n, k, u]
    foot = c.text(MX, y0 + 5 * 0.42 + 0.12, 6.7, 0.28, "test core items, as trained · words cut = longest clause, before minus after", 9.5, INK3)
    c.step((q, "fade"), *[(h, "fade", 200) for h in hdr], *[(s, "fade", 400 + 120 * i) for i, s in enumerate(table)],
           (foot, "fade", 1100), auto=True)

    bench = c.card(7.55, 2.0, 2.6, 1.7, SUN_LT, SUN, 0.12)
    b_n = c.text(7.55, 2.15, 2.6, 0.55, f"{F('bench_items'):,}", 36, SUN_DK, True, "c")
    b_l = c.text(7.55, 2.75, 2.6, 0.3, "items, split by document", 12, INK2, align="c")
    b_s = c.text(7.55, 3.05, 2.6, 0.28, f"{F('bench_dev')} dev · {F('bench_test'):,} test", 11, INK3, align="c")
    b_t = c.text(7.55, 3.35, 2.6, 0.3, "BayanBench v2", 13, SUN_DK, True, "c")
    c.step((bench, "fade"), (b_n, "fade", 200), (b_l, "fade", 350), (b_s, "fade", 500), (b_t, "fade", 650))

    src = chip(c, 7.55, 3.95, "original + rewrite", 11, PAPER2, INK2, 0.34, 2.6, False)
    gem = c.card(7.55, 4.4, 2.6, 0.85, SUN_LT, SUN, 0.12)
    g_n = c.text(7.55, 4.5, 2.6, 0.32, "Gemma 4 31B", 14, SUN_DK, True, "c")
    g_s = c.text(7.55, 4.85, 2.6, 0.28, "open model · reruns anywhere", 9.5, INK3, align="c")
    out = chip(c, 7.55, 5.4, "7 yes/no → P(yes)", 11, PAPER2, INK2, 0.34, 2.6, False)
    qa = c.card(MX, 4.55, 3.2, 1.55)
    qa_t = c.text(MX + 0.1, 4.62, 3.0, 0.3, "Meaning · 4 questions", 12, SUN_DK, True, "c")
    qa_b = c.text(MX + 0.1, 4.95, 3.0, 1.05,
                  "same meaning?  kept = yes ≥ 0.5\nand every number kept\nadds a fact?  drops a fact?\ncontradicts?", 10, INK2, line_spacing=0.95)
    qb = c.card(MX + 3.45, 4.55, 3.2, 1.55)
    qb_t = c.text(MX + 3.55, 4.62, 3.0, 0.3, "Quality · 3, diagnostic", 12, INK3, True, "c")
    qb_b = c.text(MX + 3.55, 4.95, 3.0, 1.05,
                  "Arabic correct?  coherent?\neasier to read?\npeople barely agree: never\nused to decide", 10, INK3, line_spacing=0.95)
    c.step((src, "fade"), (gem, "fade", 200), (g_n, "fade", 300), (g_s, "fade", 400), (out, "fade", 500),
           (qa, "fade", 700), (qa_t, "fade", 800), (qa_b, "fade", 900), (qb, "fade", 1000), (qb_t, "fade", 1100), (qb_b, "fade", 1200))

    auc = c.text(MX, 6.35, 2.4, 0.4, f"AUC {F('judge_auc_human')}", 22, SUN, True, "c")
    auc_l = c.text(MX + 2.5, 6.35, 4.2, 0.4, f"scorer vs {F('rater_n')} human raters\n{F('human_tasks')} tasks", 11, INK2, anchor="m")
    reader = chip(c, 7.55, 6.35, f"reader with dyslexia: {F('reader_easier')} easier / {F('reader_same')} same / {F('reader_harder')} harder", 10, PAPER2, INK2, 0.4, 2.6, False)
    c.step((auc, "fade"), (auc_l, "fade", 250), (reader, "fade", 500))
    c.finish(slide_notes("S5Measure"))


# ---- 6 · Results -------------------------------------------------------------
def s6(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "05 · Results", "v0.3 is our best model")

    sx, sy, sw2, sh2 = 0.9, 1.65, 5.0, 3.7
    ax_h = c.line(sx, sy + sh2, sx + sw2, sy + sh2, INK4, 1.5)
    ax_v = c.line(sx, sy, sx, sy + sh2, INK4, 1.5)
    xl = c.text(sx, sy + sh2 + 0.12, sw2, 0.25, "meaning kept (%)  →", 11, INK3, align="c")
    yl = c.text(sx - 0.7, sy + sh2 / 2 - 0.2, 1.4, 0.4, "clause words\nshorter  →", 11, INK3, align="c")

    pts_shapes = []
    for lab, mx, my, mark in SCATTER:
        px = sx + (mx - 35) / 70 * sw2
        py = sy + sh2 - (my + 0.5) / 7.5 * sh2
        col = {"copy": INK4, "app": SUN_DK, "model2": INK3, "ship": WARN, "baseline": INK4}.get(mark, INK3)
        r = 0.11 if mark != "ship" else 0.15
        dot = c.circle(px, py, r, col)
        pts_shapes.append(dot)
        if mark in ("copy", "ship", "app"):
            tag_col = WARN if mark == "ship" else INK2
            side = -0.75 if (mark == "ship" and mx > 60) else -0.7
            tag = c.text(px + (0.18 if side > 0 else -1.55), py - 0.32 if my > 3 else py + 0.16, 1.5, 0.25,
                         lab, 10, tag_col, mark == "ship", "c")
            pts_shapes.append(tag)
    badge = c.text(sx, sy + sh2 + 0.42, 5.0, 0.25, "BayanBench v2 · test core · as trained", 9.5, INK3)
    c.step((ax_h, "fade"), (ax_v, "fade"), (xl, "fade", 200), (yl, "fade", 200),
           *[(s, "fade", 500 + 150 * i) for i, s in enumerate(pts_shapes)], (badge, "fade", 1400), auto=True)

    side = [
        chip(c, 6.35, 1.65, "the more it simplifies,\nthe less meaning it keeps", 11, PAPER2, INK2, 0.55, 3.85, False),
        chip(c, 6.35, 2.35, f"v0.3 keeps {F('v03_kept')}% meaning\nand cuts {F('v03_clause')} words", 12, SUN, NIGHT, 0.55, 3.85),
        chip(c, 6.35, 3.05, "the app's large model,\nfour beams + safety net", 11, PAPER2, INK2, 0.55, 3.85, False),
    ]
    c.step(*[(s, "fade", 200 * i) for i, s in enumerate(side)])

    sub = c.text(MX, 5.55, CW, 0.28, "In the app: v0.3 minus v0.2, same text step · 95% intervals", 11, INK3)
    rows = [
        (f"+{F('v03_clause_diff')} words cut from the longest clause", True),
        (f"+{F('v03_hard_diff')} hard words removed", True),
        (f"{F('v03_kept_diff')} points meaning kept · not significant", True),
        (f"+{F('v03_easy_diff')} points more easy text unchanged · every number kept", True),
    ]
    chips = [chip(c, MX, 5.9 + i * 0.32, t, 10.5, SUN_LT if ok else WARN_LT, SUN_DK if ok else WARN, 0.28, 6.8, False)
             for i, (t, ok) in enumerate(rows)]
    c.step((sub, "fade"), *[(s, "fade", 250 + 180 * i) for i, s in enumerate(chips)])

    head = c.text(MX, 6.55, CW, 0.28,
                  f"Blind rating, {F('hm_sentences')} sentences: v0.3 easier on {F('hm_v03_easier')}% of changed outputs "
                  f"(v0.2 {F('hm_v02_easier')}%) · {F('hm_votes')} of {F('hm_votes')} votes", 11, INK, True, "c")
    c.step((head, "fade"))
    c.finish(slide_notes("S6Results"))


# ---- 7 · Demo ----------------------------------------------------------------
def s7(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 7, "06 · On a phone", "")

    body = c.rect(3.5, 1.4, 2.8, 4.8, NIGHT, INK4, 2, 0.28)
    scr = c.rect(3.65, 1.55, 2.5, 4.5, PAPER2, radius=0.15)
    slot = c.card(3.9, 2.3, 2.0, 2.0, PAPER3, PAPER3, 0.12)
    icon = c.text(3.9, 2.8, 2.0, 0.6, "▶", 36, INK3, align="c")
    cap = c.text(3.9, 4.45, 2.0, 0.3, "30 s recording", 13, INK2, True, "c")
    seq = c.text(3.65, 4.85, 2.5, 0.35, "select → تبسيط → sheet → read aloud", 10, INK3, align="c")

    side_items = [
        "Text selected in a browser",
        "Tap تبسيط in the menu",
        "The sheet shows the simpler text",
        "and reads it aloud",
        "The original is one tap away",
    ]
    side_shapes = [c.text(6.8, 1.85, 3.5, 0.3, "What you are watching", 14, INK, True)]
    for i, t in enumerate(side_items):
        col = SUN_LT if i == 4 else PAPER2
        tc = SUN_DK if i == 4 else INK2
        side_shapes.append(chip(c, 6.8, 2.35 + i * 0.52, t, 11, col, tc, 0.38, 3.4))

    c.step((body, "fade"), (scr, "fade", 200), (slot, "fade", 500), (icon, "fade", 700),
           (cap, "fade", 900), (seq, "fade", 1100), *[(s, "fade", 1400 + 150 * i) for i, s in enumerate(side_shapes)])
    c.finish(slide_notes("S7Phone"))


# ---- 8 · Close ---------------------------------------------------------------
def s8(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 8, dark=True)
    logo = c.pic(ASSETS / "bayan-horizontal-dark.png", (SW - 3.9) / 2, 1.25, 3.9, "Bayan logo", "Bayan logo")
    line = c.text(0, 3.2, SW, 0.7, "Simplify where you read.", 34, CREAM, True, "c")
    c.step((logo, "fade"), (line, "fade", 500), auto=True)

    limits = [
        chip(c, 2.5, 4.2, "no reader has used Bayan yet", 12, NIGHT2, INK4, 0.4, 2.8, False),
        chip(c, 5.55, 4.2, "Arabic fluency is still a gap", 12, NIGHT2, INK4, 0.4, 2.8, False),
    ]
    thanks = c.text(0, 5.15, SW, 0.35, "Thank you  ·  Team Cogni  ·  Samsung Innovation Campus", 13, SUN, align="c")
    c.step(*[(s, "fade", 200 * i) for i, s in enumerate(limits)], (thanks, "fade", 800))
    c.finish(slide_notes("S8Close"))


def main():
    prs = Presentation(TEMPLATE)
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    layout = next(l for l in prs.slide_layouts if l.name == "Body")
    for build in (s1, s2, s3, s4, s5, s6, s7, s8):
        build(prs, layout)
    prs.save(OUT)
    print(f"{OUT.name}: {len(prs.slides)} slides, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
