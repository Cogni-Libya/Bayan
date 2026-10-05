"""SUBMISSION deck: PowerPoint-native. Every element is an editable shape or text box; animations are PowerPoint's own
entrance/exit effects. Eight scenes mirroring the presenting deck's Manim layouts beat for beat.

    python build_native.py  -> ../Bayan_Submission.pptx

Fonts: Readex Pro (Latin), Noto Naskh Arabic and Amiri (Arabic). Install them before opening.
Every number comes from facts.py; check_numbers.py must pass first.

Layout is a direct port of scenes.py: Manim's centered, y-up frame (W x H units) maps to the
slide's inches with a uniform scale. Stages that Manim fades out are faded out here too.
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
TOTAL = 8

# ---- Manim frame -> slide inches ---------------------------------------------
# common.py: frame_width = 8 * 9902825 / 6858000, frame_height = 8
WM, HM = 8 * 9902825 / 6858000, 8.0
S = SH / HM  # uniform scale (== SW/WM)


def F(key):
    return FIG[key][0]


def X(x):
    return (x + WM / 2) * S


def Y(y):
    return (HM / 2 - y) * S


def U(n):
    return n * S


def box(cx, cy, w, h):
    """Top-left + size in inches for a Manim-sized box centered at (cx, cy)."""
    return X(cx) - U(w) / 2, Y(cy) - U(h) / 2, U(w), U(h)


def _tw(text, size):
    """Rough text width in inches (Readex/Naskh at `size` pt)."""
    lines = text.split("\n")
    arabic = any("\u0600" <= ch <= "\u06ff" for ch in text)
    k = 0.072 if arabic else 0.058
    return max(k * size * len(ln) for ln in lines) / 72 * 72  # size already in pt


def fit_size(text, size, max_w_in, min_size=11):
    """Shrink font so the longest line fits max_w_in (never grows)."""
    while size > min_size and _tw(text, size) > max_w_in:
        size -= 0.5
    return size


# ---- shared pieces (ports of common.chrome / chip / source_badge / scatter) ---
def chrome(c, num, kicker=None, title=None, dark=False):
    fg = CREAM if dark else INK
    items = []
    if kicker:
        kx, ky, kw, kh = X(-WM / 2 + 0.7), Y(HM / 2 - 0.75), U(6), U(0.34)
        k = c.text(kx, ky, kw, kh, kicker.upper(), 18, SUN, True, font=LATIN)
        bar = c.rect(kx - U(0.28), ky - U(0.06), U(0.08), kh + U(0.12), SUN)
        items += [bar, k]
        ty = ky + kh + U(0.28)
        t = c.text(kx, ty, U(WM - 1.4), U(0.7), title, 40, fg, True, font=LATIN)
        items.append(t)
    sam = c.pic(ASSETS / ("samsung-white.png" if dark else "samsung-blue.png"), X(-WM / 2 + 0.7), Y(-HM / 2 + 0.5), U(1.25),
                "Samsung", "Samsung logo")
    sic = c.text(X(-WM / 2 + 0.7) + U(1.25) + U(0.3), Y(-HM / 2 + 0.5), U(4.5), U(0.28),
                 "Samsung Innovation Campus  ·  AI Course", 13, CREAM if dark else INK3)
    n = c.text(X(WM / 2 - 0.7) - U(1.0), Y(-HM / 2 + 0.5), U(1.0), U(0.28), f"{num} / {TOTAL}", 13,
               CREAM if dark else INK3, align="r")
    return items + [sam, sic, n]


def chip(c, cx=0, cy=0, text="", size=15, fill=SUN_LT, color=SUN_DK, bold=True, align="c", left=None):
    """Rounded label. Positioned by center (cx,cy) in Manim coords, or left-aligned at Manim x=`left`."""
    pad = U(0.35)
    tw = _tw(text, size) * 0.98
    w = tw + 2 * pad
    h = U(0.32 + size / 72 * 1.35)
    if left is not None:
        x = X(left)
        y = Y(cy) - h / 2
    else:
        x, y = X(cx) - w / 2, Y(cy) - h / 2
    return c.card(x, y, w, h, fill, fill, radius=min(0.2 * S, h / 2), text=text, size=size, color=color,
                  bold=bold, align=align)


def source_badge(c, x, y, text, size=11):
    """Sun bar + provenance text. x,y is the text's top-left in inches."""
    bar = c.rect(x, y + U(0.04), U(0.06), U(size * 0.028), SUN)
    t = c.text(x + U(0.14) + U(0.14), y, U(6), U(size / 72 * 1.4), text, size, INK3)
    return [bar, t]


def stagger(shapes, start=0, step=150):
    return [(s, "fade", start + step * i) for i, s in enumerate(shapes)]


def out(shapes):
    """fade-out effects for a stage that Manim replaces."""
    return [(s, "fade_out", 0, 400) for s in shapes]


# =============================================================================
# 1 · Cover
# =============================================================================
def s1(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 1, dark=True)
    mx, my, mw, mh = box(0, 1.75, 3.4, 3.4)
    logo = c.pic(ASSETS / "bayan-mark-dark.png", mx, my, mw, "Bayan logo: open book with a sun", "Bayan logo")
    title = c.text(0, Y(1.75 - 1.7 - 0.35 - 0.5), SW, U(1.0), "Bayan", 72, CREAM, True, "c")
    sub = c.text(0, Y(0.2), SW, U(0.5), "Simplify Arabic where you read", 26, CREAM, align="c")
    tag = c.text(0, Y(-0.45), SW, U(0.35), "on the phone, offline", 18, SUN, align="c")
    team = c.text(0, Y(-1.15), SW, U(0.4), "Team Cogni", 22, SUN, True, "c")
    names = c.text(X(-WM / 2 + 0.8), Y(-1.75), U(WM - 1.6), U(0.3),
                   "Marwan Elamami · Abdulrahman Khengari · Ahmed Alaeb · Sanad Ali · "
                   "Mohammed Thabet · Abdul Majid Mraied", 13, INK4, align="c")
    c.step((logo, "wipe_left", 0, 1500), (title, "fade", 1300), (sub, "fade", 1700),
           (tag, "fade", 2000), (team, "fade", 2200), (names, "fade", 2300), auto=True)
    c.finish(slide_notes("S1Cover"))


# =============================================================================
# 2 · Problem
# =============================================================================
def s2(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 2, "01 · The problem", "Reading in Arabic adds load")

    # -- step 1: prevalence + one form, three readings
    num = c.text(X(-3.3) - U(1.4), Y(0.85) - U(0.75), U(2.8), U(1.5), "11%", 110, SUN, False, "c")
    lab = c.text(X(-3.3) - U(2.2), Y(0.85 - 0.75 - 0.3 - 0.35), U(4.4), U(0.8),
                 "of Arab primary-school children\nhave developmental dyslexia", 22, INK2, align="c", line_spacing=0.9)
    src_x, src_y = X(-3.3 - 2.2), Y(0.85 - 0.75 - 0.3 - 0.7 - 0.3) - U(0.1)
    src = source_badge(c, src_x, src_y, f"Al-Dakhil 2024 · {F('dyslexia_studies')} studies, N = {F('dyslexia_n'):,}")

    px, py, pw, ph = box(2.55, 0.2, 5.0, 3.9)
    panel = c.card(px, py, pw, ph)
    word = c.text(px, Y(0.2 + 1.95 - 0.95) - U(0.55), pw, U(1.1), "كتب", 100, INK, False, "c", ARABIC_DISPLAY)
    cap = c.text(px, Y(0.2 + 1.95 - 0.95 - 0.55 - 0.12) - U(0.2), pw, U(0.3), "one written form", 15, INK3, align="c")
    cols = [(3.9, "كَتَبَ", "kataba", "he wrote"), (0.0, "كُتِبَ", "kutiba", "it was written"), (-3.9, "كُتُب", "kutub", "books")]
    arrows, reads = [], []
    for x, ar, tr, en in cols:
        ax = X(x)
        arrows.append(c.line(X(0), Y(-1.25), ax, Y(-1.55), SUN, 2.5, arrow=True))
        reads.append(c.text(ax - U(0.9), Y(-1.55) - U(0.35), U(1.8), U(0.7), ar, 40, INK, False, "c", ARABIC_DISPLAY))
        reads.append(c.text(ax - U(0.9), Y(-2.35) - U(0.3), U(1.8), U(0.55),
                            [(tr, 15, SUN_DK, True, LATIN), (en, 13, SUN_DK, False, LATIN)], 13, align="c"))
    step1 = [num, lab, *src, panel, word, cap, *arrows, *reads]
    c.step(*stagger(step1[:3], 0, 300), (panel, "fade", 600), (word, "fade", 800), (cap, "fade", 1000),
           *[(a, "fade", 1200 + 250 * i) for i, a in enumerate(arrows)],
           *[(r, "fade", 1300 + 250 * (i // 2)) for i, r in enumerate(reads)], auto=True)

    # -- step 2: what helps + scope (replaces step 1)
    hx, hy, hw, hh = box(-2.6, 0.1, 4.6, 3.3)
    helps = c.card(hx, hy, hw, hh)
    h_t = c.text(hx, hy + U(0.25), hw, U(0.4), "What helps", 20, INK, True, "c")
    h_b = c.text(hx + U(0.2), hy + U(0.85), hw - U(0.4), U(1.6),
                 "Splitting long clauses into\nshort sentences: read faster,\nunderstood better, most by\nthe weakest readers.",
                 16, INK2, align="c", line_spacing=0.95)
    h_s = source_badge(c, hx + U(0.3), hy + hh - U(0.55), "Javourey-Bonnet 2022")
    sx, sy, sw, sh = box(2.6, 0.1, 4.6, 3.3)
    scope = c.card(sx, sy, sw, sh, SUN_LT, SUN, 0.18)
    s_t = c.text(sx, sy + U(0.25), sw, U(0.4), "Bayan's scope", 20, SUN_DK, True, "c")
    s_a = chip(c, 2.6, -0.35, "we reduce reading load", 16, PAPER, SUN_DK)
    s_b = chip(c, 2.6, -0.95, "long clauses · hard words", 15, PAPER, INK2, bold=False)
    s_c = chip(c, 2.6, -1.55, "not decoding · no reader claim yet", 14, WARN_LT, WARN, bold=False)
    c.step(*out(step1), (helps, "fade", 400), (h_t, "fade", 500), (scope, "fade", 500), (s_t, "fade", 600),
           (h_b, "fade", 900), (h_s[0], "fade", 1100), (h_s[1], "fade", 1100),
           (s_a, "fade", 1200), (s_b, "fade", 1400), (s_c, "fade", 1600))
    c.finish(slide_notes("S2Problem"))


# =============================================================================
# 3 · Data
# =============================================================================
def s3(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data", "How we got to corpus v1")

    def panel(x, title, lines, fill=PAPER2, stroke=PAPER3, tcol=INK):
        cx, cy, w, h = box(x, 0.1, 4.6, 3.3)
        card = c.card(cx, cy, w, h, fill, stroke, 0.18)
        t = c.text(cx, cy + U(0.25), w, U(0.4), title, 19, tcol, True, "c")
        chips = []
        for i, ln in enumerate(lines):
            chips.append(chip(c, x, -0.55 - 0.55 * i, ln, 14, PAPER, INK2, bold=False))
        return [card, t, *chips]

    a = panel(-2.6, "SAMER · human-written", [
        "novels, short sentences",
        f"{F('samer_identity_lo')}–{F('samer_identity_hi')}% of pairs unchanged",
        f"length ratio {F('samer_ratio'):.2f}: swaps words, never splits"])
    b = panel(2.6, "Other sources · LLM-written", [
        "many targets are summaries",
        "they drop facts, delete options",
        f"after a meaning filter: {F('external_kept'):,} pairs"])
    c.step((a[0], "fade"), (a[1], "fade", 200), *stagger(a[2:], 500, 250),
           (b[0], "fade", 1400), (b[1], "fade", 1600), *stagger(b[2:], 1900, 250), auto=True)
    stage1 = a + b

    # -- step 2: corpus v0 + audit
    flow_titles = ["DeepSeek: 5 candidates\nper source", "LLM equivalence\nvalidator", "CAMeL readability\ngate"]
    flow, farr = [], []
    xs = [-2.8, 0.0, 2.8]
    for i, t in enumerate(flow_titles):
        flow.append(chip(c, xs[i], 1.55, t, 14, PAPER2, INK2, bold=False))
        if i:
            farr.append(c.line(X(xs[i - 1] + 1.3), Y(1.55), X(xs[i] - 1.3), Y(1.55), SUN, 2.5, arrow=True))
    v0 = c.text(0, Y(2.25), SW, U(0.3), "corpus v0, our first synthetic data", 14, INK3, align="c")
    head = c.text(X(-WM / 2 + 0.7), Y(0.55) - U(0.2), U(5), U(0.4), "What the audit found", 18, INK, True)
    defects = [chip(c, cy=0.05 - 0.5 * i, text=t, size=15, fill=WARN_LT, color=WARN,
                    left=-WM / 2 + 0.7) for i, t in enumerate([
                        f"{int(F('v0_tashkeel') + 0.5)}% of rows had tashkeel",
                        f"{int(F('v0_completed') + 0.5)}% of cut-off sources were simply completed",
                        f"only {int(F('v0_levels') + 0.5)}% of pairs were 2+ levels easier"])]
    note = chip(c, 0, -2.4,
                f"the validator accepted {int(F('v0_validator_added') + 0.5)}% of planted added sentences · we trained nothing on v0",
                14, PAPER2, INK2, bold=False)
    stage2 = [v0, *flow, *farr, head, *defects, note]
    c.step(*out(stage1), (v0, "fade", 400), (flow[0], "fade", 500),
           (farr[0], "fade", 700), (flow[1], "fade", 800), (farr[1], "fade", 900), (flow[2], "fade", 1000),
           (head, "fade", 1200), *stagger(defects, 1400, 250), (note, "fade", 2200))

    # -- step 3: v1 lanes
    c.step(*out(stage2), auto=True)

    def lane(caption, cx, rows):
        parts = []
        parts.append(c.text(X(cx) - U(2.25), Y(1.85), U(4.5), U(0.28), caption.upper(), 13, SUN, True, "c"))
        for i, (title, sub) in enumerate(rows):
            x, y, w, h = box(cx, 0.95 - 1.1 * i, 4.5, 0.82)
            parts.append(c.card(x, y, w, h, PAPER2, PAPER3, 0.16))
            ts = fit_size(title, 17, U(4.2) * 72 / 72)
            parts.append(c.text(x + U(0.15), y + U(0.08), w - U(0.3), U(0.32), title, 17, INK, True, "c"))
            parts.append(c.text(x + U(0.15), y + U(0.42), w - U(0.3), U(0.28), sub, 12, INK3, align="c"))
            if i:
                parts.append(c.line(X(cx), Y(0.95 - 1.1 * (i - 1) - 0.41), X(cx), Y(0.95 - 1.1 * i + 0.41), SUN, 2, arrow=True))
        return parts

    left = lane("v1 · from the source", -2.5, [
        ("BAREC train + dev", "test never enters"),
        ("strip tashkeel and tatweel", "every text"),
        ("route each source", f"protected · short · hard  →  {F('route_hard'):,} hard"),
    ])
    right = lane("v1 · into the corpus", 2.5, [
        ("Gemma 4 31B writes candidates", f"hard band only  →  {F('gen_responses'):,} responses"),
        ("code gates", "numbers · quotes · options"),
        ("readability + meaning gates", f"≥ 2 levels · meaning gate  →  {F('accepted_tier_a'):,} accepted"),
    ])
    c.step(*stagger(left[:2], 0, 300), *stagger(left[2:], 600, 250),
           *stagger(right[:2], 1600, 300), *stagger(right[2:], 2200, 250))

    # -- step 4: total + audit
    arrow = c.line(X(-2.5 + 2.25), Y(0.95 + 0.9), X(2.5 - 2.25), Y(0.95 + 0.9), SUN, 3, arrow=True)
    bx, by, bw, bh = box(-2.5, -2.3, 4.4, 0.95)
    boxr = c.card(bx, by, bw, bh, SUN_LT, SUN, 0.16)
    big = c.text(bx, by + U(0.12), bw, U(0.4), f"{F('corpus_rows'):,} rows", 28, SUN_DK, True, "c")
    sub = c.text(bx, by + U(0.55), bw, U(0.28), "0 rule violations · 0 leakage vs BAREC test", 13, INK2, align="c")
    audit = chip(c, left=0.45, cy=-2.3, text=f"blind audit of {F('audit_n'):,} pairs: {F('audit_changed')}% meaning changed",
                 size=15, fill=PAPER2, color=INK2, bold=False)
    c.step((arrow, "fade"), (boxr, "fade", 300), (big, "fade", 450), (sub, "fade", 600), (audit, "fade", 900))
    c.finish(slide_notes("S3Data"))


# =============================================================================
# 4 · Models
# =============================================================================
def s4(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "03 · BayanSimplify models", "Each version answered the last failure")

    defs = [
        ("v0.1", "AraT5v2 on SAMER",
         "SAMER level 5 → 3,\n14,343 pairs",
         f"Returned {int(F('m1_copy_pct') + 0.5)}% of rows\nunchanged (editors: {int(F('m1_editor_copy_pct') + 0.5)}%).\nSwapped words, never\nrestructured."),
        ("v0.2", "AraT5v2 (v0.2) and AraBART (v0.2-Fast)",
         "SAMER + everyday text +\nmeaning-filtered pairs + tags",
         f"v0.2 keeps the meaning in\n{int(F('t5_tag_kept') + 0.5)}% of outputs, v0.2-Fast\nin {int(F('bart_tag_kept') + 0.5)}%. The tag costs\nmeaning."),
        ("v0.3", "AraT5v2 on corpus v1",
         f"corpus v1, {F('corpus_rows'):,} rows,\nno tag",
         f"Our best: cuts {F('bt_m3_clause')} words from\nthe longest clause vs {F('t5_untag_clause')}, with\nabout the same meaning\n(vs v0.2, no tag)."),
    ]
    cols, arrows = [], []
    cw, gap = 2.95, 0.45
    x0 = -((3 * cw + 2 * gap) / 2) + cw / 2
    for i, (name, what, data, found) in enumerate(defs):
        cx = x0 + i * (cw + gap)
        parts = []
        lbl = c.text(X(cx) - U(cw / 2), Y(1.55), U(cw), U(0.55), what, 14 if i == 1 else 13,
                     SUN_DK if i == 1 else INK3, i == 1, "c")
        parts.append(lbl)
        hx, hy, hw, hh = box(cx, 0.95, cw, 0.6)
        parts.append(c.card(hx, hy, hw, hh, SUN if i == 2 else PAPER3, SUN if i == 2 else PAPER3, 0.12))
        parts.append(c.text(hx, hy, hw, hh, name, 20, NIGHT if i == 2 else INK, True, "c"))
        dx, dy, dw, dh = box(cx, 0.15, cw, 1.05)
        parts.append(c.card(dx, dy, dw, dh))
        parts.append(c.text(dx + U(0.1), dy + U(0.08), dw - U(0.2), dh - U(0.16), data, 14, INK2, align="c", line_spacing=0.95))
        fx, fy, fw, fh = box(cx, -1.15, cw, 1.3)
        parts.append(c.card(fx, fy, fw, fh, WARN_LT, WARN_LT, 0.12))
        parts.append(c.text(fx + U(0.1), fy + U(0.08), fw - U(0.2), fh - U(0.16), found, 13, WARN, align="c", line_spacing=0.95))
        cols.append(parts)
        if i:
            arrows.append(c.line(X(x0 + (i - 1) * (cw + gap) + cw / 2), Y(0.95),
                                 X(cx - cw / 2), Y(0.95), SUN, 3, arrow=True))

    c.step(*stagger(cols[0], 0, 120), auto=True)
    c.step((arrows[0], "wipe_left", 0, 400), *stagger(cols[1], 300, 120))
    c.step((arrows[1], "wipe_left", 0, 400), *stagger(cols[2], 300, 120),
           (chip(c, -1.2, -2.35, "Tried and dropped:", 13, PAPER, INK3, bold=False), "fade", 1200),
           (chip(c, 0.6, -2.35, "student DPO", 12, PAPER2, INK3, bold=False), "fade", 1350),
           (chip(c, 2.1, -2.35, "minimum-risk training", 12, PAPER2, INK3, bold=False), "fade", 1500),
           (chip(c, 4.0, -2.35, "fluency retrain", 12, PAPER2, INK3, bold=False), "fade", 1650))
    c.finish(slide_notes("S4Models"))


# =============================================================================
# 5 · Measuring
# =============================================================================
def s5(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")

    # -- step 1: copy-baseline table + bench card
    q = c.text(X(-WM / 2 + 0.7), Y(1.95) - U(0.28), U(6.2), U(0.55), "Copying is the baseline to beat", 26, INK, True)
    rows_def = [
        ("Copy the input", 100, 0.0, True),
        ("v0.1", F("bt_m1_kept"), F("bt_m1_clause"), False),
        ("v0.2 (AraT5v2)", F("t5_untag_kept"), F("t5_untag_clause"), False),
        ("v0.2-Fast (AraBART)", F("bart_untag_kept"), F("bart_untag_clause"), False),
        ("v0.3", F("bt_m3_kept"), F("bt_m3_clause"), False),
    ]
    hdr = [
        c.text(X(-1.1) - U(0.8), Y(1.3) - U(0.18), U(1.6), U(0.35), "meaning kept", 12, INK3, align="c"),
        c.text(X(0.75 + 0.55) - U(1.0), Y(1.3) - U(0.28), U(2.0), U(0.5), "words cut from\nthe longest clause", 12, INK3,
               align="c", line_spacing=0.9),
    ]
    table = []
    for i, (name, kept, cut, base) in enumerate(rows_def):
        y = 0.6 - 0.58 * i
        bx, by, bw, bh = box(-1.75, y, 6.6, 0.46)
        table.append(c.card(bx, by, bw, bh, SUN_LT if base else PAPER2, SUN_LT if base else PAPER3, 0.12))
        table.append(c.text(bx + U(0.15), by, U(3.2), bh, name, 15, INK, base or name == "v0.3"))
        table.append(c.text(bx + U(3.35), by, U(1.3), bh, f"{kept:.0f}%", 15, SUN_DK, True, "c"))
        cutlab = "0" if cut < 0.05 else f"{cut:.1f}"
        table.append(c.text(bx + U(4.8), by, U(1.5), bh, cutlab, 15, SUN_DK if cut >= 0.05 else WARN, True, "c"))
    foot = c.text(X(-1.75) - U(3.3), Y(-2.45) - U(0.18), U(6.6), U(0.35),
                  "Words cut = the longest clause of a sentence, before minus after · BayanSimplify models, test core items, as trained",
                  11, INK3, align="c")
    bx, by, bw, bh = box(3.7, 0.1, 3.0, 3.0)
    bench = c.card(bx, by, bw, bh, SUN_LT, SUN, 0.16)
    b_n = c.text(bx, by + U(0.55), bw, U(0.7), f"{F('bench_items'):,}", 44, SUN_DK, True, "c")
    b_l = c.text(bx, by + U(1.35), bw, U(0.3), "items, split by document", 15, INK2, align="c")
    b_s = c.text(bx, by + U(1.75), bw, U(0.3), f"{F('bench_dev')} dev · {F('bench_test'):,} test", 14, INK3, align="c")
    b_t = c.text(bx, by + bh - U(0.5), bw, U(0.35), "BayanBench v2", 16, SUN_DK, True, "c")
    step1 = [q, *hdr, *table, foot, bench, b_n, b_l, b_s, b_t]
    c.step((q, "fade"), *stagger(hdr, 200, 150), *stagger(table, 500, 100),
           (foot, "fade", 1600), (bench, "fade", 1800), (b_n, "fade", 1900), (b_l, "fade", 2000),
           (b_s, "fade", 2100), (b_t, "fade", 2200), auto=True)

    # -- step 2: Gemma + question cards (replaces step 1)
    src_c = chip(c, -3.2, 1.65, "original + rewrite", 15, PAPER2, INK2, bold=False)
    gx, gy, gw, gh = box(0, 1.65, 2.9, 0.95)
    gem_box = c.card(gx, gy, gw, gh, SUN_LT, SUN, 0.14)
    g_n = c.text(gx, gy + U(0.12), gw, U(0.35), "Gemma 4 31B", 20, SUN_DK, True, "c")
    g_s = c.text(gx, gy + U(0.52), gw, U(0.28), "open model · reruns anywhere", 12, INK3, align="c")
    out_c = chip(c, 3.2, 1.65, "7 yes/no questions → P(yes)", 15, PAPER2, INK2, bold=False)
    arr1 = c.line(X(-3.2 + 1.6), Y(1.65), X(-1.45), Y(1.65), SUN, 2.5, arrow=True)
    arr2 = c.line(X(1.45), Y(1.65), X(3.2 - 1.8), Y(1.65), SUN, 2.5, arrow=True)

    def qcard(x, title, rows, hi=None, sub=None):
        cx, cy, w, h = box(x, -0.85, 4.7, 2.75)
        parts = [c.card(cx, cy, w, h)]
        parts.append(c.text(cx, cy + U(0.18), w, U(0.35), title, 17, SUN_DK, True, "c"))
        for i, r in enumerate(rows):
            parts.append(chip(c, x, -0.25 - 0.42 * i, r, 13, SUN if i == hi else PAPER,
                              NIGHT if i == hi else INK2, bold=(i == hi)))
        if sub:
            parts.append(c.text(cx + U(0.15), cy + h - U(0.5), w - U(0.3), U(0.4), sub, 11, INK3, align="c"))
        return parts

    qa = qcard(-2.6, "Meaning · 4 questions",
               ["same meaning?  kept = yes ≥ 0.5 and every number kept", "adds a fact?", "drops a fact?", "contradicts?"], hi=0)
    qb = qcard(2.6, "Quality · 3 questions, diagnostic",
               ["Arabic correct?", "coherent?", "easier to read?"], sub="people barely agree on these: never used to decide")
    stage_m = [src_c, gem_box, g_n, g_s, out_c, arr1, arr2, *qa, *qb]
    c.step(*out(step1), (src_c, "fade", 400), (arr1, "fade", 550), (gem_box, "fade", 700), (g_n, "fade", 800),
           (g_s, "fade", 900), (arr2, "fade", 1000), (out_c, "fade", 1150),
           *stagger(qa, 1500, 120), *stagger(qb, 2100, 120))

    # -- step 3: four measures (replaces step 2)
    measures = [
        ("Meaning", "Does it still say the same thing?\nSame meaning, every number intact."),
        ("Simpler", "Are long clauses shorter?\nWords cut from the longest clause."),
        ("Restraint", "Does it leave alone what should\nstay? Easy text, scripture."),
        ("Copying rate", "How often is the text returned\nunchanged? A copy counts as\nperfect meaning, so we report it."),
    ]
    grid = []
    for i, (n, expl) in enumerate(measures):
        gx, gy, gw, gh = box((-1 if i % 2 == 0 else 1) * 2.5, 1.0 - 2.05 * (i // 2), 4.5, 1.85)
        grid.append(c.card(gx, gy, gw, gh))
        grid.append(c.text(gx, gy + U(0.18), gw, U(0.4), n, 24, SUN_DK, True, "c"))
        grid.append(c.text(gx + U(0.2), gy + U(0.7), gw - U(0.4), U(1.0), expl, 14, INK2, align="c", line_spacing=0.95))
    c.step(*out(stage_m), *stagger(grid, 400, 180))

    # -- step 4: people check (replaces step 3)
    auc = c.text(X(-3.6) - U(1.2), Y(0.9) - U(0.55), U(2.4), U(1.1), f"{F('judge_auc_human')}", 64, SUN, True, "c")
    auc_l = c.text(X(-3.6) - U(2.0), Y(-0.15), U(4.0), U(0.3), "scorer vs human raters (AUC)", 14, INK2, align="c")
    auc_s = c.text(X(-3.6) - U(2.0), Y(-0.55), U(4.0), U(0.28),
                   f"{F('rater_n')} raters · {F('human_tasks')} tasks", 12, INK3, align="c")
    notes = [
        chip(c, left=-WM / 2 + 0.7, cy=-1.4, text=f"catches {F('human_caught')} of {F('human_losses')} changed outputs",
             size=13, fill=PAPER2, color=INK2, bold=False),
        chip(c, left=-WM / 2 + 0.7, cy=-1.9, text=f"fails {F('human_wrongfail')} of {F('human_kept')} that people kept: stricter",
             size=13, fill=PAPER2, color=INK2, bold=False),
        chip(c, left=-WM / 2 + 0.7, cy=-2.4, text="raters barely agree on ease", size=13, fill=WARN_LT, color=WARN, bold=False),
    ]
    px, py, pw, ph = box(2.4, -0.05, 5.0, 3.7)
    panel = c.card(px, py, pw, ph, SUN_LT, SUN, 0.16)
    r_t = c.text(px + U(0.2), py + U(0.35), pw - U(0.4), U(0.85),
                 f"A reader with dyslexia\nrated {F('reader_n')} outputs", 26, SUN_DK, True, "c", line_spacing=0.95)
    total = F("reader_easier") + F("reader_same") + F("reader_harder")
    segs = []
    sw = 4.3
    for n, col in [(F("reader_easier"), SUN), (F("reader_same"), PAPER3), (F("reader_harder"), WARN)]:
        seg_w = U(sw * n / total)
        segs.append((seg_w, col))
    x_off = px + (pw - U(sw)) / 2
    seg_shapes, labs = [], []
    for (seg_w, col), (n, name) in zip(segs, [("17", "easier"), ("9", "same"), ("4", "harder")]):
        seg_shapes.append(c.rect(x_off, py + ph * 0.52, seg_w, U(0.6), col))
        labs.append((x_off + seg_w / 2, f"{n} {name}"))
        x_off += seg_w
    lab_shapes = [c.text(lx - U(0.7), py + ph * 0.52 + U(0.75), U(1.4), U(0.3), t, 15, INK2, align="c") for lx, t in labs]
    r_c = c.text(px, py + ph - U(0.55), pw, U(0.3), "a sample of one, not a study", 12, INK3, align="c")
    c.step(*out(grid), (panel, "fade", 400), (r_t, "fade", 550),
           *stagger(seg_shapes, 800, 200), *stagger(lab_shapes, 1600, 150), (r_c, "fade", 2000),
           (auc, "fade", 2200), (auc_l, "fade", 2350), (auc_s, "fade", 2500), *stagger(notes, 2700, 200))
    c.finish(slide_notes("S5Measure"))


# =============================================================================
# 6 · Results
# =============================================================================
def s6(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "05 · Results", "v0.3 is our best model")

    # -- step 1: meaning-vs-simplicity scatter
    pw, ph = 5.2, 3.3
    px, py = -2.3, -0.25
    x0, x1, y0, y1 = 30, 105, -0.6, 7.6
    ax_h = c.line(X(px - pw / 2), Y(py - ph / 2), X(px + pw / 2), Y(py - ph / 2), INK4, 2)
    ax_v = c.line(X(px - pw / 2), Y(py - ph / 2), X(px - pw / 2), Y(py + ph / 2), INK4, 2)
    xl = c.text(X(px) - U(2.5), Y(py - ph / 2) + U(0.12), U(5.0), U(0.28), "meaning kept (%)  →", 12, INK3, align="c")
    yl = c.text(X(px - pw / 2) - U(0.55), Y(py) - U(1.2), U(0.7), U(2.4), "simplification: words cut\nfrom the longest clause  →",
                12, INK3, align="c")

    def xy(x, y):
        return X(px - pw / 2 + (x - x0) / (x1 - x0) * pw), Y(py - ph / 2 + (y - y0) / (y1 - y0) * ph)

    pts = []
    for lab, x, y, mark in SCATTER:
        col = {"copy": INK4, "baseline": INK4, "app": SUN_DK, "model2": INK3, "ship": WARN}.get(mark, INK3)
        cx, cy = xy(x, y)
        r = U(0.17 if mark == "ship" else 0.12)
        if mark == "ship":
            pts.append(c.circle(cx, cy, r * 2.1, None, line=SUN, line_w=1.5))
        pts.append(c.circle(cx, cy, r, col))
        if mark in ("copy", "baseline", "ship", "app"):
            tag_col = WARN if mark == "ship" else INK2
            if mark == "ship":
                pts.append(c.text(cx + r + U(0.1), cy - U(0.15), U(1.8), U(0.3), lab, 12, tag_col, True))
            elif mark in ("app", "baseline", "copy"):
                pts.append(c.text(cx - U(1.1), cy - U(0.45), U(2.2), U(0.28), lab, 12, tag_col, align="c"))
    badge = source_badge(c, X(px + pw / 2) - U(2.8), Y(py - ph / 2) + U(0.55), "BayanBench v2, test core items")
    side = [
        chip(c, left=1.35, cy=1.15, text="the more it simplifies,\nthe less meaning it keeps, obviously",
             size=15, fill=SUN_LT, color=SUN_DK, bold=True),
        chip(c, left=1.35, cy=0.15, text=f"v0.3 keeps the most meaning ({F('v03_kept')}%)\nand still cuts {F('v03_clause')} words off\nthe longest clause",
             size=15, fill=SUN, color=NIGHT, bold=True),
        chip(c, left=1.35, cy=-0.95, text="v0.3 is the app's large model,\ndecoded with four beams",
             size=14, fill=PAPER2, color=INK2, bold=False),
    ]
    step1 = [ax_h, ax_v, xl, yl, *pts, *badge, *side]
    c.step((ax_h, "fade"), (ax_v, "fade"), (xl, "fade", 200), (yl, "fade", 200),
           *stagger(pts, 500, 120), *[(b, "fade", 1400) for b in badge],
           *stagger(side, 1700, 250), auto=True)

    # -- step 2: forest rows (replaces step 1)
    sub = c.text(0, Y(1.95) - U(0.15), SW, U(0.3),
                 "In the app: v0.3 (four beams) minus v0.2, same text step, test core, 95% interval", 13, INK3, align="c")

    def forest_row(label, est, lo, hi, scale, fmt, y):
        lab = c.text(X(-WM / 2 + 0.7), Y(y) - U(0.15), U(4.3), U(0.3), label, 14, INK2)
        axx, half = 1.2, 2.6
        axis = c.line(X(axx - half), Y(y), X(axx + half), Y(y), PAPER3, 3)
        zero = c.line(X(axx), Y(y - 0.13), X(axx), Y(y + 0.13), INK4, 2)

        def px_of(v):
            return X(axx + max(-1, min(1, v / scale)) * half)

        ci = c.line(px_of(lo), Y(y), px_of(hi), Y(y), SUN_DK, 6)
        dot = c.circle(px_of(est), Y(y), U(0.1), SUN_DK)
        val = c.text(X(axx + half) + U(0.15), Y(y) - U(0.15), U(1.2), U(0.3), fmt(est), 14, SUN_DK, True)
        return [lab, axis, zero, ci, dot, val]

    rows = (
        forest_row("words cut from the longest clause", F("v03_clause_diff"), 2.4, 4.4, 6, lambda v: f"+{v:.1f}", 1.45)
        + forest_row("hard words removed", F("v03_hard_diff"), 0.14, 0.35, 0.4, lambda v: f"+{v:.2f}", 0.9)
        + forest_row("reading levels lowered", F("v03_level_diff"), 0.0, 0.16, 0.3, lambda v: f"+{v:.2f}", 0.35)
        + forest_row("meaning kept (points): no significant difference", F("v03_kept_diff"), -7, 1, 15,
                     lambda v: f"{v:+.0f}".replace("-", "−"), -0.2)
    )
    chipA = chip(c, 0, -1.05,
                 f"+{F('v03_easy_diff')} points more easy text left unchanged · every number kept ({F('v03_numbers')}%)",
                 14, SUN_LT, SUN_DK, bold=True)
    stage2 = [sub, *rows, chipA]
    c.step(*out(step1), (sub, "fade", 400), *stagger(rows, 700, 200), (chipA, "fade", 2000))

    # -- step 3: blind rating (replaces step 2)
    head = c.text(0, Y(1.95) - U(0.2), SW, U(0.4),
                  f"Blind rating by the team: {F('hm_sentences')} sentences", 18, INK, True, "c")
    sub2 = c.text(0, Y(1.95 - 0.45), SW, U(0.28), "outputs the system changed, rated easier to read", 13, INK3, align="c")
    bars = []
    for i, (name, pct, col) in enumerate([("v0.3", F("hm_v03_easier"), SUN), ("v0.2", F("hm_v02_easier"), PAPER3),
                                          ("v0.2-Fast", F("hm_fast_easier"), PAPER3)]):
        y = 0.95 - 0.62 * i
        bars.append(c.text(X(-4.3), Y(y) - U(0.15), U(1.5), U(0.3), name, 15, INK, i == 0))
        bw = U(6.0 * pct / 100)
        bars.append(c.rect(X(-2.4), Y(y) - U(0.21), bw, U(0.42), col))
        bars.append(c.text(X(-2.4) + bw + U(0.12), Y(y) - U(0.15), U(0.9), U(0.3), f"{pct}%", 15, SUN_DK if i == 0 else INK2, True))
    chipD = chip(c, 0, -1.15,
                 f"meaning kept in {F('hm_v03_same')}% of ratings (v0.2: {F('hm_v02_same')}%, v0.2-Fast: {F('hm_fast_same')}%) · none rated harder",
                 14, PAPER2, INK2, bold=False)
    chipE = chip(c, 0, -1.7, f"{F('hm_votes')} of {F('hm_votes')} team votes chose v0.3 over v0.2", 15, SUN_LT, SUN_DK)
    n_cmp = F("hm_reader_v03_v02") + F("hm_reader_v03_fast")
    chipF = chip(c, 0, -2.3,
                 f"the reader with dyslexia chose v0.3 in {n_cmp} of {n_cmp} comparisons it was in · "
                 f"{F('hm_sentences')} sentences: a direction, not a size",
                 13, PAPER2, INK2, bold=False)
    c.step(*out(stage2), (head, "fade", 400), (sub2, "fade", 550),
           *stagger(bars, 800, 180), (chipD, "fade", 1800), (chipE, "fade", 2100), (chipF, "fade", 2400))
    c.finish(slide_notes("S6Results"))


# =============================================================================
# 7 · On a phone
# =============================================================================
def s7(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 7, "06 · On a phone", "")
    head = c.text(0, Y(2.0) - U(0.28), SW, U(0.55), "What the app does", 26, INK, True, "c")
    bx, by, bw, bh = box(0, -0.5, 2.75, 4.3)
    body = c.rect(bx, by, bw, bh, NIGHT, INK4, 2, 0.3)
    scr = c.rect(bx + U(0.12), by + U(0.12), bw - U(0.24), bh - U(0.24), PAPER2, radius=0.18)
    icon = c.text(bx, by + bh / 2 - U(0.55), bw, U(1.0), "▶", 44, INK3, align="c")
    cap = c.text(bx, by + bh / 2 + U(0.55), bw, U(0.3), "recording goes here", 13, INK3, align="c")
    c.step((head, "fade"), (body, "fade", 400), (scr, "fade", 550), (icon, "fade", 700), (cap, "fade", 850))
    c.finish(slide_notes("S7Phone"))


# =============================================================================
# 8 · Close
# =============================================================================
def s8(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 8, dark=True)
    mx, my, mw = X(0) - U(2.4) / 2, Y(2.0) - U(1.4), U(2.4)
    logo = c.pic(ASSETS / "bayan-mark-dark.png", mx, my, mw, "Bayan logo", "Bayan logo")
    line = c.text(0, Y(2.0 - 1.2 - 0.35 - 0.35), SW, U(0.7), "Simplify where you read.", 36, CREAM, True, "c")
    c.step((logo, "fade"), (line, "fade", 400), auto=True)

    limits = [
        chip(c, 0, -1.35, "no reader has used Bayan; one reader rated 30 outputs", 15, NIGHT2, INK4, bold=False),
        chip(c, 0, -1.9, "our scorer is stricter than people", 15, NIGHT2, INK4, bold=False),
        chip(c, 0, -2.45, f"the comparison with people covers {F('hm_sentences')} sentences", 15, NIGHT2, INK4, bold=False),
    ]
    nxt = c.text(0, Y(-3.15), SW, U(0.35), "Next: a reading study with more readers.", 17, SUN, align="c")
    thanks = c.text(0, Y(-3.65), SW, U(0.3), "Thank you  ·  Team Cogni  ·  Samsung Innovation Campus", 14, INK4, align="c")
    c.step(*stagger(limits, 0, 250), (nxt, "fade", 1000), (thanks, "fade", 1300))
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
