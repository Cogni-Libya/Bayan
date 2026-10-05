"""SUBMISSION deck: PowerPoint-native. One slide per presenting step (same order the HTML player
clicks through), so the deck looks right in PowerPoint, in a PDF and on paper — not only in an
animation-aware slideshow.

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

# content frame, inches (slide is 10.83 x 7.5)
ML, MR = 0.62, 0.62
CW = SW - ML - MR
CT, CB = 1.62, 6.72  # below kicker/title, above footer


def F(key):
    return FIG[key][0]


def R(x):
    return int(x + 0.5)


# ---- text metrics ------------------------------------------------------------
def text_w(s, size):
    """Approximate rendered width in inches for Readex/Naskh at `size` pt."""
    widest = 0
    for line in s.split("\n"):
        w = 0.0
        for ch in line:
            if "\u0600" <= ch <= "\u06ff":
                w += 0.62
            elif ch in "iljI.,:;'|!":
                w += 0.28
            elif ch in "mwMW":
                w += 0.85
            elif ch.isupper():
                w += 0.68
            else:
                w += 0.55
        widest = max(widest, w)
    return widest * size / 72.0


def text_h(s, size, width=None):
    lines = s.split("\n")
    if width:
        est = text_w(s, size)
        if est > width:
            lines = lines * int(est / width + 1)  # conservative: assume wrap
    return len(lines) * size / 72.0 * 1.28


# ---- primitives --------------------------------------------------------------
def chrome(c, num, kicker=None, title=None, dark=False):
    fg = CREAM if dark else INK
    if kicker:
        c.rect(ML, 0.52, 0.07, 0.30, SUN)
        c.text(ML + 0.18, 0.48, CW - 0.2, 0.34, kicker.upper(), 12.5, SUN, True)
    if title:
        c.text(ML, 0.88, CW, 0.55, title, 26, fg, True)
    sam = c.pic(ASSETS / ("samsung-white.png" if dark else "samsung-blue.png"), ML, 6.93, 1.12, "Samsung", "Samsung logo")
    c.text(ML + 1.28, 6.98, 4.2, 0.28, "Samsung Innovation Campus  ·  AI Course", 10, CREAM if dark else INK3)
    c.text(SW - MR - 1.0, 6.98, 1.0, 0.28, f"{num} / 8", 10, CREAM if dark else INK3, align="r")
    return sam


def chip(c, x, y, text, size=13, fill=SUN_LT, color=SUN_DK, bold=True, max_w=None, align="c"):
    """Label pill at (x,y) top-left. Width follows the text; `max_w` only shrinks the font."""
    if max_w:
        while size > 10.5 and text_w(text, size) + 0.5 > max_w:
            size -= 0.5
    w = min(text_w(text, size) + 0.52, max_w or CW)
    h = text_h(text, size) + 0.16
    return c.card(x, y, w, h, fill, fill, radius=0.09, text=text, size=size, color=color, bold=bold, align=align)


def chip_c(c, cx, y, text, **kw):
    """Chip centered on cx (inches)."""
    size = kw.get("size", 13)
    max_w = kw.get("max_w")
    if max_w:
        while size > 10.5 and text_w(text, size) + 0.5 > max_w:
            size -= 0.5
            kw["size"] = size
    w = min(text_w(text, size) + 0.52, max_w or CW)
    return chip(c, cx - w / 2, y, text, **kw)


def badge(c, x, y, text, size=10.5):
    c.rect(x, y + 0.03, 0.05, 0.16, SUN)
    c.text(x + 0.12, y, 6.5, 0.22, text, size, INK3)
    return y + 0.22


def card_text(c, x, y, w, h, title, body, fill=PAPER2, stroke=PAPER3, tcol=INK, bcol=INK2,
              tsize=15, bsize=12, gap=0.06):
    card = c.card(x, y, w, h, fill, stroke, 0.12)
    th = text_h(title, tsize)
    c.text(x + 0.1, y + 0.12, w - 0.2, th + 0.06, title, tsize, tcol, True, "c")
    if body:
        c.text(x + 0.14, y + 0.12 + th + gap, w - 0.28, h - 0.24 - th - gap, body, bsize, bcol, align="c",
               line_spacing=1.0)
    return card


# =============================================================================
# Beat 1 · Cover — 1 slide
# =============================================================================
def s1(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 1, dark=True)
    c.pic(ASSETS / "bayan-mark-dark.png", (SW - 3.1) / 2, 0.88, 3.1, "Bayan logo", "Bayan logo")
    c.text(0, 4.15, SW, 0.85, "Bayan", 56, CREAM, True, "c")
    c.text(0, 5.05, SW, 0.42, "Simplify Arabic where you read", 20, CREAM, align="c")
    c.text(0, 5.52, SW, 0.32, "on the phone, offline", 14, SUN, align="c")
    c.text(0, 6.0, SW, 0.34, "Team Cogni", 15, SUN, True, "c")
    c.text(ML, 6.38, CW, 0.28,
           "Marwan Elamami · Abdulrahman Khengari · Ahmed Alaeb · Sanad Ali · "
           "Mohammed Thabet · Abdul Majid Mraied", 10, INK4, align="c")
    c.finish(slide_notes("S1Cover"))


# =============================================================================
# Beat 2 · Problem — 2 slides
# =============================================================================
def s2a(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 2, "01 · The problem", "Reading in Arabic adds load")
    # left: prevalence
    c.text(ML, 1.85, 3.5, 1.15, "11%", 84, SUN, False, "c")
    c.text(ML, 3.05, 3.5, 0.75, "of Arab primary-school children\nhave developmental dyslexia", 15, INK2,
           align="c", line_spacing=1.05)
    badge(c, ML + 0.35, 3.95, f"Al-Dakhil 2024 · {F('dyslexia_studies')} studies, N = {F('dyslexia_n'):,}")
    # right: one form, three readings
    px, py, pw, ph = 4.45, 1.72, 5.75, 3.55
    c.card(px, py, pw, ph)
    c.text(px, py + 0.18, pw, 0.95, "كتب", 68, INK, False, "c", ARABIC_DISPLAY)
    c.text(px, py + 1.18, pw, 0.28, "one written form", 12, INK3, align="c")
    readings = [("كَتَبَ", "kataba", "he wrote"), ("كُتِبَ", "kutiba", "it was written"), ("كُتُب", "kutub", "books")]
    cw = 1.7
    x0 = px + (pw - 3 * cw) / 2
    for i, (ar, tr, en) in enumerate(readings):
        x = x0 + i * cw
        c.line(px + pw / 2, py + 1.55, x + cw / 2, py + 1.85, SUN, 2, arrow=True)
        c.text(x, py + 1.9, cw, 0.55, ar, 30, INK, False, "c", ARABIC_DISPLAY)
        c.text(x, py + 2.55, cw, 0.55, [(tr, 12, SUN_DK, True, LATIN), (en, 11, SUN_DK, False, LATIN)], 12, align="c")
    c.finish(slide_notes("S2Problem"))


def s2b(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 2, "01 · The problem", "Reading in Arabic adds load")
    hw, hh, hy = 4.75, 4.35, 1.9
    hx, sx = ML, ML + hw + 0.35
    c.card(hx, hy, hw, hh)
    c.text(hx, hy + 0.22, hw, 0.38, "What helps", 18, INK, True, "c")
    c.text(hx + 0.35, hy + 0.95, hw - 0.7, 2.3,
           "Splitting long clauses into\nshort sentences: read faster,\nunderstood better, most by\nthe weakest readers.",
           15, INK2, align="c", line_spacing=1.15)
    badge(c, hx + 0.55, hy + hh - 0.55, "Javourey-Bonnet 2022")

    c.card(sx, hy, hw, hh, SUN_LT, SUN, 0.14)
    c.text(sx, hy + 0.22, hw, 0.38, "Bayan's scope", 18, SUN_DK, True, "c")
    chip_c(c, sx + hw / 2, hy + 1.15, "we reduce reading load", size=15, fill=PAPER, color=SUN_DK, max_w=hw - 0.5)
    chip_c(c, sx + hw / 2, hy + 1.85, "long clauses · hard words", size=14, fill=PAPER, color=INK2, bold=False,
           max_w=hw - 0.5)
    chip_c(c, sx + hw / 2, hy + 2.55, "not decoding · no reader claim yet", size=13, fill=WARN_LT, color=WARN,
           bold=False, max_w=hw - 0.5)
    c.finish(slide_notes("S2Problem"))


# =============================================================================
# Beat 3 · Data — 4 slides
# =============================================================================
def s3a(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data", "How we got to corpus v1")
    hw, hh, hy = 4.75, 4.45, 1.85
    for x, title, lines in [
        (ML, "SAMER · human-written", [
            "novels, short sentences",
            f"{F('samer_identity_lo')}–{F('samer_identity_hi')}% of pairs unchanged",
            f"length ratio {F('samer_ratio'):.2f}: swaps words, never splits"]),
        (ML + hw + 0.35, "Other sources · LLM-written", [
            "many targets are summaries",
            "they drop facts, delete options",
            f"after a meaning filter: {F('external_kept'):,} pairs"]),
    ]:
        c.card(x, hy, hw, hh)
        c.text(x, hy + 0.22, hw, 0.38, title, 17, INK, True, "c")
        for i, ln in enumerate(lines):
            chip_c(c, x + hw / 2, hy + 1.15 + i * 0.85, ln, size=13, fill=PAPER, color=INK2, bold=False,
                   max_w=hw - 0.45)
    c.finish(slide_notes("S3Data"))


def s3b(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data", "How we got to corpus v1")
    c.text(ML, 1.62, CW, 0.28, "corpus v0, our first synthetic data", 12, INK3, align="c")
    steps = ["DeepSeek: 5 candidates\nper source", "LLM equivalence\nvalidator", "CAMeL readability\ngate"]
    bw, gap = 2.7, 0.55
    x0 = ML + (CW - 3 * bw - 2 * gap) / 2
    for i, t in enumerate(steps):
        x = x0 + i * (bw + gap)
        c.card(x, 2.05, bw, 0.85, PAPER2, PAPER3, 0.1, t, 12, INK2, False)
        if i:
            c.line(x - gap, 2.47, x, 2.47, SUN, 2, arrow=True)
    c.text(ML, 3.25, CW, 0.38, "What the audit found", 17, INK, True)
    defects = [
        f"{R(F('v0_tashkeel'))}% of rows had tashkeel",
        f"{R(F('v0_completed'))}% of cut-off sources were simply completed",
        f"only {R(F('v0_levels'))}% of pairs were 2+ levels easier",
    ]
    for i, t in enumerate(defects):
        chip(c, ML, 3.72 + i * 0.52, t, size=13, fill=WARN_LT, color=WARN, max_w=CW)
    chip(c, ML, 5.5, f"the validator accepted {R(F('v0_validator_added'))}% of planted added sentences · "
                     f"we trained nothing on v0", size=12, fill=PAPER2, color=INK2, bold=False, max_w=CW)
    c.finish(slide_notes("S3Data"))


def s3c(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data", "How we got to corpus v1")

    def lane(x, caption, rows):
        w = 4.75
        c.text(x, 1.62, w, 0.28, caption.upper(), 11, SUN, True, "c")
        for i, (title, sub) in enumerate(rows):
            y = 2.05 + i * 1.28
            c.card(x, y, w, 1.05, PAPER2, PAPER3, 0.12)
            c.text(x + 0.12, y + 0.18, w - 0.24, 0.32, title, 14, INK, True, "c")
            c.text(x + 0.12, y + 0.58, w - 0.24, 0.3, sub, 11, INK3, align="c")
            if i:
                c.line(x + w / 2, y - 0.2, x + w / 2, y, SUN, 2, arrow=True)

    lane(ML, "v1 · from the source", [
        ("BAREC train + dev", "test never enters"),
        ("strip tashkeel and tatweel", "every text"),
        ("route each source", f"protected · short · hard  →  {F('route_hard'):,} hard"),
    ])
    lane(ML + 4.75 + 0.35, "v1 · into the corpus", [
        ("Gemma 4 31B writes candidates", f"hard band only  →  {F('gen_responses'):,} responses"),
        ("code gates", "numbers · quotes · options"),
        ("readability + meaning gates", f"≥ 2 levels · meaning gate  →  {F('accepted_tier_a'):,} accepted"),
    ])
    c.finish(slide_notes("S3Data"))


def s3d(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 3, "02 · Data", "How we got to corpus v1")
    # keep the lanes as a quiet backdrop row of captions
    c.text(ML, 1.7, CW, 0.3, "from the source  →  into the corpus", 13, INK3, align="c")
    bx, by, bw, bh = ML, 2.35, 5.1, 1.25
    c.card(bx, by, bw, bh, SUN_LT, SUN, 0.12)
    c.text(bx, by + 0.18, bw, 0.55, f"{F('corpus_rows'):,} rows", 30, SUN_DK, True, "c")
    c.text(bx, by + 0.78, bw, 0.3, "0 rule violations · 0 leakage vs BAREC test", 12, INK2, align="c")
    chip(c, ML + bw + 0.4, 2.55,
         f"blind audit of {F('audit_n'):,} pairs:\n{F('audit_changed')}% meaning changed",
         size=14, fill=PAPER2, color=INK2, bold=False, max_w=CW - bw - 0.5)
    chip_c(c, SW / 2, 4.35, "every gate in corpus v1 exists because of a failure we saw",
           size=14, fill=SUN_LT, color=SUN_DK, max_w=CW)
    c.finish(slide_notes("S3Data"))


# =============================================================================
# Beat 4 · Models — 3 slides
# =============================================================================
MODELS = [
    ("v0.1", "AraT5v2 on SAMER", "SAMER level 5 → 3,\n14,343 pairs",
     f"Returned {R(F('m1_copy_pct'))}% of rows unchanged\n(editors: {R(F('m1_editor_copy_pct'))}%).\nSwapped words, never restructured."),
    ("v0.2", "AraT5v2 + AraBART", "SAMER + everyday text +\nmeaning-filtered pairs + tags",
     f"v0.2 keeps the meaning in {R(F('t5_tag_kept'))}%\nof outputs, v0.2-Fast in {R(F('bart_tag_kept'))}%.\nThe tag costs meaning."),
    ("v0.3", "AraT5v2 on corpus v1", f"corpus v1, {F('corpus_rows'):,} rows,\nno tag",
     f"Our best: cuts {F('bt_m3_clause')} words from the\nlongest clause vs {F('t5_untag_clause')}, with about\nthe same meaning (vs v0.2, no tag)."),
]


def _model_col(c, x, y, w, i, show=True):
    name, what, data, found = MODELS[i]
    if not show:
        return
    c.text(x, y, w, 0.32, what, 11.5, SUN_DK if i == 1 else INK3, i == 1, "c")
    head_fill = SUN if i == 2 else PAPER3
    c.card(x, y + 0.38, w, 0.52, head_fill, head_fill, 0.1, name, 17, NIGHT if i == 2 else INK, True)
    c.card(x, y + 1.02, w, 1.15, PAPER2, PAPER3, 0.1, data, 12, INK2, False)
    c.card(x, y + 2.28, w, 1.55, WARN_LT, WARN_LT, 0.1)
    c.text(x + 0.12, y + 2.42, w - 0.24, 1.3, found, 11.5, WARN, align="c", line_spacing=1.08)


def s4a(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "03 · BayanSimplify models", "Each version answered the last failure")
    w = 3.05
    x = ML + (CW - 3 * w - 2 * 0.55) / 2
    _model_col(c, x, 2.05, w, 0)
    c.finish(slide_notes("S4Models"))


def s4b(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "03 · BayanSimplify models", "Each version answered the last failure")
    w, gap = 3.05, 0.55
    x0 = ML + (CW - 3 * w - 2 * gap) / 2
    _model_col(c, x0, 2.05, w, 0)
    c.line(x0 + w + 0.06, 3.15, x0 + w + gap - 0.06, 3.15, SUN, 2.5, arrow=True)
    _model_col(c, x0 + w + gap, 2.05, w, 1)
    c.finish(slide_notes("S4Models"))


def s4c(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 4, "03 · BayanSimplify models", "Each version answered the last failure")
    w, gap = 3.05, 0.55
    x0 = ML + (CW - 3 * w - 2 * gap) / 2
    for i in range(3):
        _model_col(c, x0 + i * (w + gap), 2.05, w, i)
        if i:
            c.line(x0 + i * (w + gap) - gap + 0.06, 3.15, x0 + i * (w + gap) - 0.06, 3.15, SUN, 2.5, arrow=True)
    y = 6.05
    c.text(ML, y, 1.6, 0.28, "Tried and dropped:", 11, INK3)
    x = ML + 1.65
    for t in ["student DPO", "minimum-risk training", "fluency retrain"]:
        ch = chip(c, x, y - 0.02, t, size=11, fill=PAPER2, color=INK3, bold=False)
        x += text_w(t, 11) + 0.75
    c.finish(slide_notes("S4Models"))


# =============================================================================
# Beat 5 · Measuring — 4 slides
# =============================================================================
def s5a(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")
    c.text(ML, 1.62, 6.6, 0.42, "Copying is the baseline to beat", 20, INK, True)
    rows_def = [
        ("Copy the input", 100, 0.0, True),
        ("v0.1", F("bt_m1_kept"), F("bt_m1_clause"), False),
        ("v0.2 (AraT5v2)", F("t5_untag_kept"), F("t5_untag_clause"), False),
        ("v0.2-Fast (AraBART)", F("bart_untag_kept"), F("bart_untag_clause"), False),
        ("v0.3", F("bt_m3_kept"), F("bt_m3_clause"), False),
    ]
    tw = 6.7
    c.text(ML + 3.4, 2.12, 1.3, 0.28, "meaning kept", 10.5, INK3, align="c")
    c.text(ML + 4.85, 2.12, 1.7, 0.28, "words cut from\nthe longest clause", 10.5, INK3, align="c", line_spacing=0.95)
    for i, (name, kept, cut, base) in enumerate(rows_def):
        y = 2.5 + i * 0.52
        c.card(ML, y, tw, 0.44, SUN_LT if base else PAPER2, SUN_LT if base else PAPER3, 0.08)
        c.text(ML + 0.18, y + 0.06, 3.1, 0.32, name, 13, INK, base or name == "v0.3")
        c.text(ML + 3.4, y + 0.06, 1.3, 0.32, f"{kept:.0f}%", 13, SUN_DK, True, "c")
        cutlab = "0" if cut < 0.05 else f"{cut:.1f}"
        c.text(ML + 4.85, y + 0.06, 1.7, 0.32, cutlab, 13, SUN_DK if cut >= 0.05 else WARN, True, "c")
    c.text(ML, 5.35, tw, 0.28,
           "test core items, as trained · words cut = longest clause, before minus after", 10, INK3, align="c")

    bx, by, bw, bh = ML + tw + 0.35, 2.5, 2.55, 2.85
    c.card(bx, by, bw, bh, SUN_LT, SUN, 0.12)
    c.text(bx, by + 0.35, bw, 0.6, f"{F('bench_items'):,}", 32, SUN_DK, True, "c")
    c.text(bx, by + 1.05, bw, 0.28, "items, split by document", 12, INK2, align="c")
    c.text(bx, by + 1.45, bw, 0.28, f"{F('bench_dev')} dev · {F('bench_test'):,} test", 11, INK3, align="c")
    c.text(bx, by + bh - 0.5, bw, 0.32, "BayanBench v2", 13, SUN_DK, True, "c")
    c.finish(slide_notes("S5Measure"))


def s5b(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")
    # flow
    chip_c(c, 2.3, 1.75, "original + rewrite", size=13, fill=PAPER2, color=INK2, bold=False)
    gx, gw, gh = 3.85, 2.75, 1.05
    c.card(gx, 1.65, gw, gh, SUN_LT, SUN, 0.1)
    c.text(gx, 1.78, gw, 0.35, "Gemma 4 31B", 16, SUN_DK, True, "c")
    c.text(gx, 2.18, gw, 0.28, "open model · reruns anywhere", 11, INK3, align="c")
    chip_c(c, 8.55, 1.75, "7 yes/no → P(yes)", size=13, fill=PAPER2, color=INK2, bold=False)
    c.line(3.35, 2.2, 3.8, 2.2, SUN, 2, arrow=True)
    c.line(6.65, 2.2, 7.15, 2.2, SUN, 2, arrow=True)

    def qcard(x, title, rows, hi=None, sub=None):
        w, h = 4.85, 2.85
        c.card(x, 3.15, w, h)
        c.text(x, 3.32, w, 0.35, title, 15, SUN_DK, True, "c")
        for i, r in enumerate(rows):
            chip_c(c, x + w / 2, 3.85 + i * 0.42, r, size=11.5,
                   fill=SUN if i == hi else PAPER, color=NIGHT if i == hi else INK2,
                   bold=(i == hi), max_w=w - 0.4)
        if sub:
            c.text(x + 0.2, 3.15 + h - 0.48, w - 0.4, 0.4, sub, 10, INK3, align="c")

    qcard(ML, "Meaning · 4 questions",
          ["same meaning?  kept = yes ≥ 0.5\nand every number kept", "adds a fact?", "drops a fact?", "contradicts?"],
          hi=0)
    qcard(ML + 4.85 + 0.35, "Quality · 3 questions, diagnostic",
          ["Arabic correct?", "coherent?", "easier to read?"],
          sub="people barely agree on these: never used to decide")
    c.finish(slide_notes("S5Measure"))


def s5c(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")
    measures = [
        ("Meaning", "Does it still say the same thing?\nSame meaning, every number intact."),
        ("Simpler", "Are long clauses shorter?\nWords cut from the longest clause."),
        ("Restraint", "Does it leave alone what should\nstay? Easy text, scripture."),
        ("Copying rate", "How often is the text returned unchanged?\nA copy counts as perfect meaning,\nso we report it."),
    ]
    w, h, gap = 4.85, 2.15, 0.35
    x0 = ML + (CW - 2 * w - gap) / 2
    for i, (n, expl) in enumerate(measures):
        x = x0 + (i % 2) * (w + gap)
        y = 1.95 + (i // 2) * (h + gap)
        c.card(x, y, w, h)
        c.text(x, y + 0.22, w, 0.42, n, 20, SUN_DK, True, "c")
        c.text(x + 0.25, y + 0.85, w - 0.5, h - 1.05, expl, 13, INK2, align="c", line_spacing=1.1)
    c.finish(slide_notes("S5Measure"))


def s5d(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 5, "04 · BayanBench", "We checked our own yardstick")
    # left: AUC + notes
    c.text(ML, 2.0, 3.2, 0.95, f"{F('judge_auc_human')}", 60, SUN, False, "c")
    c.text(ML, 3.05, 3.2, 0.3, "scorer vs human raters (AUC)", 13, INK2, align="c")
    c.text(ML, 3.4, 3.2, 0.28, f"{F('rater_n')} raters · {F('human_tasks')} tasks", 11, INK3, align="c")
    for i, t in enumerate([
        f"catches {F('human_caught')} of {F('human_losses')} changed outputs",
        f"fails {F('human_wrongfail')} of {F('human_kept')} people kept: stricter",
        "raters barely agree on ease",
    ]):
        chip(c, ML, 4.0 + i * 0.55, t, size=11.5, fill=WARN_LT if i == 2 else PAPER2,
             color=WARN if i == 2 else INK2, bold=False, max_w=3.6)

    # right: reader panel
    px, py, pw, ph = ML + 3.85, 1.85, CW - 3.85, 4.35
    c.card(px, py, pw, ph, SUN_LT, SUN, 0.12)
    c.text(px + 0.2, py + 0.35, pw - 0.4, 0.85,
           f"A reader with dyslexia\nrated {F('reader_n')} outputs", 20, SUN_DK, True, "c", line_spacing=1.05)
    total = F("reader_easier") + F("reader_same") + F("reader_harder")
    bw = pw - 1.0
    x = px + 0.5
    for n, name, col in [(F("reader_easier"), "easier", SUN), (F("reader_same"), "same", PAPER3),
                         (F("reader_harder"), "harder", WARN)]:
        seg = bw * n / total
        c.rect(x, py + 1.75, seg, 0.55, col)
        c.text(x, py + 2.45, seg, 0.3, f"{n} {name}", 13, INK2, align="c")
        x += seg
    c.text(px, py + ph - 0.55, pw, 0.3, "a sample of one, not a study", 11, INK3, align="c")
    c.finish(slide_notes("S5Measure"))


# =============================================================================
# Beat 6 · Results — 3 slides
# =============================================================================
def s6a(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "05 · Results", "v0.3 is our best model")
    # scatter
    ox, oy, pw, ph = ML + 0.55, 1.85, 5.35, 3.85
    c.line(ox, oy + ph, ox + pw, oy + ph, INK4, 1.5)
    c.line(ox, oy, ox, oy + ph, INK4, 1.5)
    c.text(ox, oy + ph + 0.1, pw, 0.26, "meaning kept (%)  →", 11, INK3, align="c")
    c.text(ML - 0.05, oy + ph / 2 - 0.35, 1.05, 0.7, "clause words\nshorter  →", 11, INK3, align="c")
    x0, x1, y0, y1 = 30, 105, -0.6, 7.6

    def xy(x, y):
        return ox + (x - x0) / (x1 - x0) * pw, oy + ph - (y - y0) / (y1 - y0) * ph

    for lab, x, y, mark in SCATTER:
        col = {"copy": INK4, "baseline": INK4, "app": SUN_DK, "model2": INK3, "ship": WARN}.get(mark, INK3)
        px, py = xy(x, y)
        r = 0.11 if mark != "ship" else 0.14
        if mark == "ship":
            c.circle(px, py, r + 0.1, None, line=SUN, line_w=1.5)
        c.circle(px, py, r, col)
        if mark in ("copy", "baseline", "ship", "app"):
            tc = WARN if mark == "ship" else INK2
            if mark == "ship":
                c.text(px + 0.2, py - 0.16, 1.7, 0.28, lab, 11, tc, True)
            else:
                c.text(px - 0.95, py - 0.42, 1.9, 0.26, lab, 11, tc, align="c")
    badge(c, ox + 0.15, oy + ph + 0.45, "BayanBench v2, test core items")

    side_x = ox + pw + 0.55
    side_w = SW - MR - side_x
    chip(c, side_x, 2.05, "the more it simplifies,\nthe less meaning it keeps", size=13,
         fill=PAPER2, color=INK2, bold=False, max_w=side_w)
    chip(c, side_x, 3.05, f"v0.3 keeps the most meaning ({F('v03_kept')}%)\nand still cuts {F('v03_clause')} words",
         size=13, fill=SUN, color=NIGHT, max_w=side_w)
    chip(c, side_x, 4.15, "the app's large model,\nfour beams + safety net", size=12,
         fill=PAPER2, color=INK2, bold=False, max_w=side_w)
    c.finish(slide_notes("S6Results"))


def s6b(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "05 · Results", "v0.3 is our best model")
    c.text(ML, 1.62, CW, 0.28,
           "In the app: v0.3 minus v0.2, same text step · 95% intervals", 12, INK3, align="c")

    def row(y, label, est, lo, hi, scale, fmt):
        c.text(ML, y, 3.9, 0.28, label, 12, INK2)
        ax, half = 5.7, 1.85
        c.line(ax - half, y + 0.16, ax + half, y + 0.16, PAPER3, 3)
        c.line(ax, y + 0.03, ax, y + 0.29, INK4, 1.5)

        def px_of(v):
            return ax + max(-1, min(1, v / scale)) * half

        c.line(px_of(lo), y + 0.16, px_of(hi), y + 0.16, SUN_DK, 5)
        c.circle(px_of(est), y + 0.16, 0.08, SUN_DK)
        c.text(ax + half + 0.12, y + 0.02, 1.1, 0.28, fmt(est), 12, SUN_DK, True)

    rows = [
        ("words cut from the longest clause", F("v03_clause_diff"), 2.4, 4.4, 6, lambda v: f"+{v:.1f}"),
        ("hard words removed", F("v03_hard_diff"), 0.14, 0.35, 0.4, lambda v: f"+{v:.2f}"),
        ("reading levels lowered", F("v03_level_diff"), 0.0, 0.16, 0.3, lambda v: f"+{v:.2f}"),
        ("meaning kept (points): not significant", F("v03_kept_diff"), -7, 1, 15,
         lambda v: f"{v:+.0f}".replace("-", "−")),
    ]
    for i, r in enumerate(rows):
        row(2.25 + i * 0.72, *r)
    chip_c(c, SW / 2, 5.5,
           f"+{F('v03_easy_diff')} points more easy text unchanged · every number kept ({F('v03_numbers')}%)",
           size=13, fill=SUN_LT, color=SUN_DK, max_w=CW)
    c.finish(slide_notes("S6Results"))


def s6c(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 6, "05 · Results", "v0.3 is our best model")
    c.text(ML, 1.62, CW, 0.36, f"Blind rating by the team: {F('hm_sentences')} sentences", 17, INK, True, "c")
    c.text(ML, 2.05, CW, 0.28, "outputs the system changed, rated easier to read", 12, INK3, align="c")
    for i, (name, pct, col) in enumerate([("v0.3", F("hm_v03_easier"), SUN), ("v0.2", F("hm_v02_easier"), PAPER3),
                                          ("v0.2-Fast", F("hm_fast_easier"), PAPER3)]):
        y = 2.65 + i * 0.62
        c.text(ML, y, 1.2, 0.32, name, 13, INK, i == 0)
        bw = 5.6 * pct / 100
        c.rect(ML + 1.35, y + 0.02, bw, 0.38, col)
        c.text(ML + 1.35 + bw + 0.12, y, 0.8, 0.32, f"{pct}%", 13, SUN_DK if i == 0 else INK2, True)
    chip_c(c, SW / 2, 4.75,
           f"meaning kept in {F('hm_v03_same')}% of ratings (v0.2: {F('hm_v02_same')}%, "
           f"v0.2-Fast: {F('hm_fast_same')}%) · none rated harder",
           size=12, fill=PAPER2, color=INK2, bold=False, max_w=CW)
    chip_c(c, SW / 2, 5.35, f"{F('hm_votes')} of {F('hm_votes')} team votes chose v0.3 over v0.2",
           size=13, fill=SUN_LT, color=SUN_DK, max_w=CW)
    n_cmp = F("hm_reader_v03_v02") + F("hm_reader_v03_fast")
    chip_c(c, SW / 2, 5.95,
           f"the reader with dyslexia chose v0.3 in {n_cmp} of {n_cmp} comparisons · "
           f"{F('hm_sentences')} sentences: a direction, not a size",
           size=11.5, fill=PAPER2, color=INK2, bold=False, max_w=CW)
    c.finish(slide_notes("S6Results"))


# =============================================================================
# Beat 7 · Phone — 1 slide
# =============================================================================
def s7(prs, layout):
    c = Canvas(prs, layout, PAPER)
    chrome(c, 7, "06 · On a phone", "")
    c.text(ML, 1.75, CW, 0.45, "What the app does", 22, INK, True, "c")
    bw, bh = 2.85, 4.15
    x = (SW - bw) / 2
    y = 2.35
    c.rect(x, y, bw, bh, NIGHT, INK4, 2, 0.26)
    c.rect(x + 0.12, y + 0.12, bw - 0.24, bh - 0.24, PAPER2, radius=0.16)
    c.text(x, y + bh / 2 - 0.55, bw, 0.85, "▶", 36, INK3, align="c")
    c.text(x, y + bh / 2 + 0.45, bw, 0.3, "recording goes here", 12, INK3, align="c")
    c.finish(slide_notes("S7Phone"))


# =============================================================================
# Beat 8 · Close — 2 slides
# =============================================================================
def s8a(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 8, dark=True)
    c.pic(ASSETS / "bayan-mark-dark.png", (SW - 2.5) / 2, 1.75, 2.5, "Bayan logo", "Bayan logo")
    c.text(0, 4.35, SW, 0.65, "Simplify where you read.", 30, CREAM, True, "c")
    c.finish(slide_notes("S8Close"))


def s8b(prs, layout):
    c = Canvas(prs, layout, NIGHT)
    chrome(c, 8, dark=True)
    c.text(0, 1.85, SW, 0.55, "Simplify where you read.", 28, CREAM, True, "c")
    for i, t in enumerate([
        "no reader has used Bayan; one reader rated 30 outputs",
        "our scorer is stricter than people",
        f"the comparison with people covers {F('hm_sentences')} sentences",
    ]):
        chip_c(c, SW / 2, 2.85 + i * 0.62, t, size=13, fill=NIGHT2, color=INK4, bold=False, max_w=CW)
    c.text(0, 5.05, SW, 0.36, "Next: a reading study with more readers.", 15, SUN, align="c")
    c.text(0, 5.55, SW, 0.3, "Thank you  ·  Team Cogni  ·  Samsung Innovation Campus", 12, INK4, align="c")
    c.finish(slide_notes("S8Close"))


STEPS = [s1, s2a, s2b, s3a, s3b, s3c, s3d, s4a, s4b, s4c, s5a, s5b, s5c, s5d, s6a, s6b, s6c, s7, s8a, s8b]


def main():
    prs = Presentation(TEMPLATE)
    ids = prs.slides._sldIdLst
    for sld in list(ids):
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    layout = next(l for l in prs.slide_layouts if l.name == "Body")
    for build in STEPS:
        build(prs, layout)
    prs.save(OUT)
    print(f"{OUT.name}: {len(prs.slides)} slides, {OUT.stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
