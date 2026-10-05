#!/usr/bin/env python3
"""Build Bayan_Final_Report.docx from the LaTeX sources + PDF figure crops.

Hybrid: editable Word text/tables styled to bayan.sty; TikZ figures are images
cropped from Bayan_Final_Report.pdf (extract_figures.py).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Emu, Mm, Pt, RGBColor, Twips

HERE = Path(__file__).resolve().parent
LATEX = HERE.parent
OUT = LATEX.parent / "Bayan_Final_Report.docx"

SIC_BLUE = "193DB0"
SIC_HEAD = "DEE5FA"
SIC_RULE = "BFBFBF"
SIC_PALE = "EEF2FC"
BODY = "000000"
FONT = "SamsungOne"
FONT_BOLD = "SamsungOne"  # bold via run.bold; family name stays SamsungOne
SHARP = "Samsung Sharp Sans"
MONO = "Liberation Mono"
ARABIC_FONT = "PakType Naskh Basic"

# Figure crops in document order (extract_figures.py output)
FIGS = [
    "fig01_schedule", "fig02_evolution", "fig03_pipeline", "fig04_architecture",
    "fig05_cleaning", "fig06_lengths", "fig07_sari", "fig08_training",
    "fig09_behaviour", "fig10_trainingtwo", "fig11_scorer", "fig12_dumbbell",
    "fig13_tradeoff", "fig14_ui",
]

MACROS: dict[str, str] = {}
FIGURE_SEQ = 0
TABLE_SEQ = 0


# ----------------------------------------------------------------- low-level
def set_run_font(run, name=FONT, size=10.5, bold=False, italic=False,
                 color=BODY, rtl=False):
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    for attr in ("w:ascii", "w:hAnsi", "w:cs"):
        rFonts.set(qn(attr), name)
    if rtl:
        lang = rPr.find(qn("w:lang"))
        if lang is None:
            lang = OxmlElement("w:lang")
            rPr.append(lang)
        lang.set(qn("w:bidi"), "ar-SA")
        lang.set(qn("w:val"), "ar-SA")
        rtl_el = OxmlElement("w:rtl")
        rPr.append(rtl_el)


def shade(element, fill):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")
    element.append(shd)


def set_cell_borders(cell, color=SIC_RULE, sz=4):
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), color)
        borders.append(el)
    tcPr.append(borders)


def para_spacing(p, before=0, after=5, line=14.2):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY
    pf.line_spacing = Pt(line)
    pf.first_line_indent = Pt(0)


def add_field(paragraph, instr):
    run = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "begin")
    run._r.append(fld)
    run = paragraph.add_run()
    it = OxmlElement("w:instrText")
    it.set(qn("xml:space"), "preserve")
    it.text = instr
    run._r.append(it)
    run = paragraph.add_run()
    fld = OxmlElement("w:fldChar")
    fld.set(qn("w:fldCharType"), "end")
    run._r.append(fld)


# ----------------------------------------------------------------- macros
def load_macros():
    names = [
        "figures.tex", "results.tex", "bench_v2.tex",
        "human.tex", "model3.tex", "human_m3.tex", "main.tex",
    ]
    for name in names:
        text = (LATEX / name).read_text(encoding="utf-8")
        for m in re.finditer(
            r"\\newcommand\{\\([A-Za-z@]+)\}\{(.*)\}",
            text, re.S,
        ):
            # only simple one-line values (skip multi-line table macros here;
            # those are handled as named block macros below)
            body = m.group(2)
            if "\\begin{" in body:
                MACROS[m.group(1)] = body
            else:
                # strip trailing junk that belonged to next command
                MACROS[m.group(1)] = body
        # multi-line newcommands: brace matcher
    for name in names:
        text = (LATEX / name).read_text(encoding="utf-8")
        for m in re.finditer(r"\\newcommand\{\\([A-Za-z@]+)\}", text):
            macro = m.group(1)
            start = m.end()
            if start >= len(text) or text[start] != "{":
                continue
            i = start
            depth = 0
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        MACROS[macro] = text[start + 1:i]
                        break
                i += 1
    MACROS.update({
        "vOne": "BayanSimplify-v0.1",
        "vTwo": "BayanSimplify-v0.2",
        "vTwoFast": "BayanSimplify-v0.2-Fast",
        "vThree": "BayanSimplify-v0.3",
        "textminus": "−",
    })


def expand(text: str) -> str:
    """Expand \\foo{} / \\foo macros that are simple value macros."""
    # Don't expand structural macros
    structural = {
        "section", "subsection", "lead", "ar", "textbf", "emph", "texttt",
        "cite", "autoref", "item", "caption", "label", "includegraphics",
        "finding", "footnote", "input", "bibitem", "makecell", "head",
        "multicolumn", "cellcolor", "hline", "resizebox", "hspace", "vspace",
        "noindent", "small", "scriptsize", "footnotesize", "tiny", "centering",
        "center", "fcolorbox", "parbox", "dimexpr", "linewidth", "enspace",
        "begin", "end", "mbox", "mathrm", "hat", "alpha", "geq", "times",
        "approx", "cdot", "emph", "thanks", "footnotemark", "footnotetext",
        "newcommand", "vOne", "vTwo", "vTwoFast", "vThree", "done", "wip",
        "todo", "resultstable", "barectable", "figsari", "figbehaviour",
        "benchheadtable", "benchothertable", "benchsetstable", "benchefftable",
        "scoreraucatable", "humansystable", "readertable", "pairstable",
        "figschedule", "figevolution", "figpipeline", "figarchitecture",
        "figcleaning", "figlengths", "figtraining", "figtrainingtwo",
        "figui", "figtradeoff", "figscorer", "figdumbbell",
        "cat", "score", "siccover", "siccontents", "addcontentsline",
        "clearpage", "null", "thispagestyle", "setlength", "setcounter",
        "renewcommand", "pagestyle", "fancyhf", "fancyfoot", "textwidth",
        "thebibliography", "endthebibliography", "hline", "vOne",
        "textminus", "member", "cat", "score",
    }
    out = text
    for name, val in MACROS.items():
        if name in structural:
            continue
        # \name{} or \name (word boundary)
        out = re.sub(r"\\" + re.escape(name) + r"(?![A-Za-z@])", val, out)
    return out


# ----------------------------------------------------------------- text runs
TOKEN_RE = re.compile(
    r"(?P<ar>\\ar\{[^{}]*\})"
    r"|(?P<lead>\\lead\{[^{}]*\})"
    r"|(?P<bf>\\textbf\{[^{}]*\})"
    r"|(?P<em>\\emph\{[^{}]*\})"
    r"|(?P<tt>\\texttt\{[^{}]*\})"
    r"|(?P<cite>\\cite\{[^{}]*\})"
    r"|(?P<ref>\\autoref\{[^{}]*\})"
    r"|(?P<fn>\\footnote\{[^{}]*\})"
    r"|(?P<math>\$[^$]*\$)"
    r"|(?P<makecell>\\makecell\{(?:[^{}]|\{[^{}]*\})*\})"
    r"|(?P<sym>\\\\|\\enspace|\\,|\\;|\\!|\\%|\\&|\\#|\\_|\$\\cdot\$)"
    r"|(?P<plain>[^\\$]+)",
)


def _inner(s: str) -> str:
    s = s.strip()
    if s.startswith("{") and s.endswith("}"):
        # peel one level of braces that wraps the whole string
        depth = 0
        for i, ch in enumerate(s):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0 and i != len(s) - 1:
                    return s
        return s[1:-1]
    # command form: \textbf{...}
    m = re.match(r"\\[A-Za-z]+\{(.*)\}$", s, re.S)
    return m.group(1) if m else s


PLAIN_MAP = {
    r"\%": "%", r"\&": "&", r"\#": "#", r"\_": "_",
    "\\enspace": " ", "\\,": " ", "\\;": " ",
    "---": "—", "--": "–", "``": "“", "''": "”",
    "\\textminus": "−", "$\\cdot$": "·", "\\cdot": "·",
    "~": " ",
}


def flatten_plain(s: str) -> str:
    for a, b in PLAIN_MAP.items():
        s = s.replace(a, b)
    s = s.replace("\\%", "%").replace("\\&", "&")
    return s


def add_rich_text(paragraph, text: str, size=10.5, color=BODY, bold=False,
                  italic=False, mono=False):
    text = expand(text)
    text = re.sub(r"%.*", "", text)  # comments
    # unify whitespace but keep intentional spaces
    text = re.sub(r"\s+", " ", text)

    pos = 0
    for m in TOKEN_RE.finditer(text):
        if m.start() > pos:
            plain = flatten_plain(text[pos:m.start()])
            if plain.strip() or plain == " ":
                r = paragraph.add_run(plain)
                set_run_font(r, MONO if mono else FONT, size, bold, italic, color)
        kind = m.lastgroup
        tok = m.group(0)
        if kind == "ar":
            inner = _inner(tok)
            r = paragraph.add_run(inner)
            set_run_font(r, ARABIC_FONT, size, bold, italic, color, rtl=True)
        elif kind == "lead":
            inner = _inner(tok)
            r = paragraph.add_run(inner + " ")
            set_run_font(r, FONT, size, True, italic, color)
        elif kind == "bf":
            add_rich_text(paragraph, _inner(tok), size, color, True, italic, mono)
        elif kind == "em":
            add_rich_text(paragraph, _inner(tok), size, color, bold, True, mono)
        elif kind == "tt":
            add_rich_text(paragraph, _inner(tok), size - 0.5, color, bold, italic, True)
        elif kind == "cite":
            keys = _inner(tok)
            label = "[" + ", ".join(
                str(i + 1) for i, _ in enumerate(keys.split(","))
            ) + "]"
            # real numbers resolved later via CITE_ORDER; placeholder key text
            label = "[" + keys + "]"
            r = paragraph.add_run(label)
            set_run_font(r, FONT, size, bold, italic, color)
        elif kind == "ref":
            inner = _inner(tok)
            r = paragraph.add_run(f"[{inner}]")
            set_run_font(r, FONT, size, bold, italic, color)
        elif kind == "fn":
            r = paragraph.add_run("†")
            set_run_font(r, FONT, size - 1, bold, italic, color)
        elif kind == "math":
            inner = tok.strip("$")
            inner = inner.replace("\\times", "×").replace("\\geq", "≥")
            inner = inner.replace("\\approx", "≈").replace("\\alpha", "α")
            inner = inner.replace("\\hat y", "ŷ").replace("\\oplus", "⊕")
            inner = inner.replace("\\leq", "≤").replace("\\ge", "≥")
            r = paragraph.add_run(inner)
            set_run_font(r, FONT, size, bold, True, color)
        elif kind == "makecell":
            inner = _inner(tok)
            # split \\ rows, drop \tiny brackets
            inner = re.sub(r"\\tiny|\\small|\\[-?\d+pt\]|\\makecell|\\bfseries", "", inner)
            parts = [flatten_plain(p) for p in inner.split(r"\\") if p.strip()]
            r = paragraph.add_run(" / ".join(p.strip() for p in parts))
            set_run_font(r, FONT, size - 1, bold, italic, color)
        elif kind == "sym":
            if tok == r"\\":
                continue
            r = paragraph.add_run(flatten_plain(tok) or " ")
            set_run_font(r, FONT, size, bold, italic, color)
        else:
            plain = flatten_plain(tok)
            if plain:
                r = paragraph.add_run(plain)
                set_run_font(r, FONT, size, bold, italic, color)
        pos = m.end()
    if pos < len(text):
        plain = flatten_plain(text[pos:])
        if plain:
            r = paragraph.add_run(plain)
            set_run_font(r, FONT, size, bold, italic, color)


# ----------------------------------------------------------------- blocks
def strip_comments(tex: str) -> str:
    out = []
    for line in tex.splitlines():
        # keep escaped \%
        line = re.sub(r"(?<!\\)%.*", "", line)
        out.append(line)
    return "\n".join(out)


def split_env_blocks(tex: str, env: str):
    """Yield (pre_text, env_body, post_text) for each \\begin{env}...\\end{env}."""
    begin = f"\\begin{{{env}}}"
    end = f"\\end{{{env}}}"
    while True:
        i = tex.find(begin)
        if i < 0:
            if tex.strip():
                yield tex, None, ""
            return
        j = tex.find(end, i)
        if j < 0:
            yield tex[:i], tex[i:], ""
            return
        body = tex[i + len(begin):j]
        yield tex[:i], body, tex[j + len(end):]
        tex = tex[j + len(end):]


def parse_table_body(body: str):
    """Parse tabular/tabularx body into rows of cells (list[list[list[str]]]).
    Each cell is a list of lines (for makecell-ish content).
    """
    # column spec is before the first \\
    # remove column spec line: {|L|...|}
    body = body.lstrip()
    m = re.match(r"\s*\{([^{}]*)\}", body)
    spec = m.group(1) if m else ""
    if m:
        body = body[m.end():]
    body = re.sub(r"\\hline|\\toprule|\\midrule|\\bottomrule", "\n", body)
    body = body.replace("\\\\", "\n")
    rows = []
    for raw in body.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^\\(hline|toprule|midrule|bottomrule)", line):
            continue
        # split on & not inside braces
        cells, cur, depth = [], [], 0
        for ch in line:
            if ch == "{":
                depth += 1
                cur.append(ch)
            elif ch == "}":
                depth -= 1
                cur.append(ch)
            elif ch == "&" and depth == 0:
                cells.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
        cells.append("".join(cur).strip())
        # drop trailing \\ leftovers
        cells = [c.replace("\\\\", "").strip() for c in cells]
        if any(cells):
            rows.append(cells)
    return spec, rows


def normalize_cell(text: str) -> tuple[str, bool, bool, bool]:
    """Return (plainish, is_header, is_band, is_center)."""
    is_header = "\\head{" in text
    is_band = "\\multicolumn" in text or "\\cellcolor{sichead}" in text
    t = text
    t = t.replace("\\head{", "{")
    t = re.sub(r"\\multicolumn\{\d+\}\{[^{}]*\}", "", t)
    t = t.replace("\\cellcolor{sichead}", "")
    t = t.replace("\\bfseries", "")
    t = t.replace("\\centering", "")
    t = t.replace("\\arraybackslash", "")
    t = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\[a-zA-Z]+", "", t)
    t = t.replace("{", "").replace("}", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t, is_header, is_band, is_header or is_band


def add_table(doc, body: str, caption: str | None, label: str | None):
    global TABLE_SEQ
    if caption:
        TABLE_SEQ += 1
        cap = doc.add_paragraph()
        para_spacing(cap, before=8, after=3, line=12)
        r = cap.add_run(f"Table {TABLE_SEQ}. ")
        set_run_font(r, FONT, 9.5, True, False, SIC_BLUE)
        add_rich_text(cap, caption, size=9.5)

    spec, rows = parse_table_body(body)
    if not rows:
        return
    ncols = max(len(r) for r in rows)
    table = doc.add_table(rows=0, cols=ncols)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = True
    # force table width to text width
    tblPr = table._tbl.tblPr
    tblW = OxmlElement("w:tblW")
    tblW.set(qn("w:type"), "pct")
    tblW.set(qn("w:w"), "5000")
    tblPr.append(tblW)

    for row in rows:
        # band row (single logical cell)
        if len(row) == 1 and ("multicolumn" in row[0] or "cellcolor" in row[0]):
            t, _, is_band, _ = normalize_cell(row[0])
            tr = table.add_row()
            merged = tr.cells[0]
            for c in tr.cells[1:]:
                merged = merged.merge(c)
            p = merged.paragraphs[0]
            para_spacing(p, 1, 1, 12)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            add_rich_text(p, row[0], size=9, bold=True)
            shade(merged._tc.get_or_add_tcPr(), SIC_HEAD)
            set_cell_borders(merged)
            continue
        tr = table.add_row()
        for i in range(ncols):
            cell = tr.cells[i]
            raw = row[i] if i < len(row) else ""
            text, is_header, is_band, center = normalize_cell(raw)
            p = cell.paragraphs[0]
            para_spacing(p, 1, 1, 11.5)
            p.alignment = (
                WD_ALIGN_PARAGRAPH.CENTER if is_header
                else WD_ALIGN_PARAGRAPH.LEFT
            )
            # re-add with formatting from raw
            cleaned = raw
            cleaned = re.sub(r"\\head\{([^{}]*)\}", r"\1", cleaned)
            cleaned = re.sub(r"\\multicolumn\{\d+\}\{[^{}]*\}", "", cleaned)
            cleaned = cleaned.replace("\\cellcolor{sichead}", "")
            cleaned = cleaned.replace("\\centering", "")
            cleaned = cleaned.replace("\\arraybackslash", "")
            cleaned = cleaned.replace("\\bfseries", "")
            cleaned = re.sub(r"\\makecell\{((?:[^{}]|\{[^{}]*\})*)\}",
                             lambda m: m.group(1).replace(r"\\", " / ")
                             .replace("\\tiny", "")
                             .replace("\\small", ""),
                             cleaned)
            cleaned = re.sub(r"\\[-\d.]+pt\]", "", cleaned)
            cleaned = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", cleaned)
            cleaned = re.sub(r"\\[a-zA-Z]+", " ", cleaned)
            cleaned = cleaned.replace("{", "").replace("}", "")
            add_rich_text(p, cleaned, size=9, bold=is_header)
            if is_header:
                shade(cell._tc.get_or_add_tcPr(), SIC_HEAD)
            set_cell_borders(cell)


def add_figure(doc, idx: int, caption: str):
    global FIGURE_SEQ
    FIGURE_SEQ += 1
    name = FIGS[idx] if idx < len(FIGS) else FIGS[-1]
    path = HERE / "figs" / f"{name}.png"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_spacing(p, 6, 2, 12)
    if path.exists():
        run = p.add_run()
        run.add_picture(str(path), width=Mm(155))
    cap = doc.add_paragraph()
    para_spacing(cap, 2, 8, 12)
    cap.alignment = WD_ALIGN_PARAGRAPH.LEFT
    r = cap.add_run(f"Figure {FIGURE_SEQ}. ")
    set_run_font(r, FONT, 9.5, True, False, SIC_BLUE)
    add_rich_text(cap, caption, size=9.5)


def add_banner(doc, title: str, numbered: str | None):
    """Blue full-bleed section banner as a 1x1 table."""
    table = doc.add_table(rows=1, cols=1)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = table.rows[0].cells[0]
    # widen to text width + 7.5mm bleed left via indent
    tcPr = cell._tc.get_or_add_tcPr()
    shade(tcPr, SIC_BLUE)
    # no borders
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tcPr.append(borders)
    p = cell.paragraphs[0]
    para_spacing(p, 2, 2, 16)
    text = f"{numbered}. {title}" if numbered else title
    r = p.add_run(text)
    set_run_font(r, FONT, 14, True, False, "FFFFFF")
    # height
    tr = table.rows[0]
    tr.height = Mm(5.4)
    tr.height_rule = WD_ROW_HEIGHT_RULE.AT_LEAST
    # spacer after
    sp = doc.add_paragraph()
    para_spacing(sp, 0, 4, 6)


def add_body_para(doc, text: str, size=10.5, before=0, after=5, indent_left=0):
    p = doc.add_paragraph()
    para_spacing(p, before, after, 14.2)
    if indent_left:
        p.paragraph_format.left_indent = Mm(indent_left)
    add_rich_text(p, text, size=size)
    return p


def add_list(doc, body: str, kind: str, label_fmt: str | None):
    items = re.split(r"\\item\b", body)
    n = 0
    for it in items[1:]:
        n += 1
        it = it.strip()
        # drop trailing junk
        it = re.sub(r"\\label\{[^}]*\}", "", it)
        p = doc.add_paragraph()
        para_spacing(p, 1, 2, 14.2)
        p.paragraph_format.left_indent = Mm(5)
        if kind == "enumerate" and label_fmt:
            if "RQ" in label_fmt:
                prefix = f"RQ{n} "
            elif "O" in label_fmt and "RQ" not in label_fmt:
                prefix = f"O{n} "
            elif "F" in label_fmt:
                prefix = f"F{n} "
            else:
                prefix = f"({chr(96 + n)}) "
            r = p.add_run(prefix)
            set_run_font(r, FONT, 10.5, True)
        else:
            r = p.add_run("• ")
            set_run_font(r, FONT, 10.5, True)
        add_rich_text(p, it, size=10.5)


def add_box(doc, body: str, fill: str, border: str, lead: str | None):
    table = doc.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    tcPr = cell._tc.get_or_add_tcPr()
    shade(tcPr, fill)
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "6")
        el.set(qn("w:color"), border)
        borders.append(el)
    tcPr.append(borders)
    p = cell.paragraphs[0]
    para_spacing(p, 3, 3, 13.5)
    if lead:
        r = p.add_run(lead + " ")
        set_run_font(r, FONT, 10.5, True, False, SIC_BLUE)
    add_rich_text(p, body, size=10.5)


# ----------------------------------------------------------------- body walk
def handle_stream(doc, tex: str):
    tex = strip_comments(tex)
    tex = expand(tex)

    # expand structural content macros (tables/figures defined in inputs)
    for name in (
        "resultstable", "barectable", "benchheadtable", "benchothertable",
        "benchsetstable", "benchefftable", "scoreraucatable", "humansystable",
        "readertable", "pairstable",
        "figsari", "figbehaviour", "figschedule", "figevolution", "figpipeline",
        "figarchitecture", "figcleaning", "figlengths", "figtraining",
        "figtrainingtwo", "figui", "figtradeoff", "figscorer", "figdumbbell",
    ):
        if name in MACROS and f"\\{name}" in tex:
            tex = tex.replace(f"\\{name}", MACROS[name])

    # Drop preamble leftovers / labels
    tex = re.sub(r"\\label\{[^}]*\}", "", tex)
    tex = re.sub(r"\\begin\{document\}|\\end\{document\}", "", tex)
    tex = re.sub(r"\\begin\{fullwidth\}|\\end\{fullwidth\}", "", tex)
    tex = re.sub(r"\\clearpage|\\newpage|\\null|\\thispagestyle\{[^}]*\}", "", tex)
    tex = re.sub(r"\\FloatBarrier|\\noindent", "", tex)
    tex = re.sub(r"\\vspace\*?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\hspace\*?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\setlength\{[^}]*\}\{[^}]*\}", "", tex)
    tex = re.sub(r"\\small|\\footnotesize|\\scriptsize|\\tiny", "", tex)
    tex = re.sub(r"\\centering", "", tex)
    tex = re.sub(r"\\begin\{center\}|\\end\{center\}", "", tex)
    tex = re.sub(r"\\itemsep|\\topsep|\\leftmargin|\\label=\{[^}]*\}", "", tex)

    while tex.strip():
        tex = tex.lstrip()
        if not tex:
            break

        # section / subsection
        m = re.match(r"\\section\*?\{([^{}]*)\}", tex)
        if m:
            title = m.group(1)
            numbered = None
            # peek: if not starred, assign number
            if not m.group(0).startswith("\\section*"):
                # count previous sections
                numbered = str(getattr(handle_stream, "sec", 0) + 1)
                handle_stream.sec = int(numbered)
                handle_stream.sub = 0
            add_banner(doc, title, numbered)
            tex = tex[m.end():]
            continue

        m = re.match(r"\\subsection\*?\{([^{}]*)\}", tex)
        if m:
            title = m.group(1)
            handle_stream.sub = getattr(handle_stream, "sub", 0) + 1
            sec = getattr(handle_stream, "sec", 0)
            p = doc.add_paragraph()
            para_spacing(p, 10, 3, 14)
            if not m.group(0).startswith("\\subsection*"):
                r = p.add_run(f"{sec}.{handle_stream.sub}. ")
                set_run_font(r, FONT, 11, True)
            add_rich_text(p, title, size=11, bold=True)
            tex = tex[m.end():]
            continue

        # finding box
        m = re.match(r"\\finding\{((?:[^{}]|\{[^{}]*\})*)\}", tex, re.S)
        if m:
            add_box(doc, m.group(1), SIC_PALE, SIC_BLUE, None)
            tex = tex[m.end():]
            continue

        # figure
        m = re.match(r"\\begin\{figure\}(.*?)\\end\{figure\}", tex, re.S)
        if m:
            block = m.group(1)
            cap_m = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\})*)\}", block, re.S)
            caption = cap_m.group(1) if cap_m else ""
            add_figure(doc, getattr(handle_stream, "figi", 0), caption)
            handle_stream.figi = getattr(handle_stream, "figi", 0) + 1
            tex = tex[m.end():]
            continue

        # table
        m = re.match(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S)
        if m:
            block = m.group(1)
            cap_m = re.search(r"\\caption\{((?:[^{}]|\{[^{}]*\}|\n)*?)\}(?:\s*\\label\{[^}]*\})?",
                              block, re.S)
            caption = cap_m.group(1) if cap_m else ""
            tab_m = re.search(
                r"\\begin\{tabularx?\}\s*\{[^{}]*\}\s*\{[^{}]*\}(.*?)\\end\{tabularx?\}",
                block, re.S,
            )
            if tab_m:
                add_table(doc, tab_m.group(1), caption or None, None)
            tex = tex[m.end():]
            continue

        # bare tabularx (glance Q/A)
        m = re.match(
            r"\\begin\{tabularx?\}\s*\{[^{}]*\}\s*\{[^{}]*\}(.*?)\\end\{tabularx?\}",
            tex, re.S,
        )
        if m:
            add_table(doc, m.group(1), None, None)
            tex = tex[m.end():]
            continue

        # lists
        m = re.match(
            r"\\begin\{(itemize|enumerate)\}(\s*\[[^\]]*\])?(.*?)\\end\{\1\}",
            tex, re.S,
        )
        if m:
            kind = m.group(1)
            opts = m.group(2) or ""
            label_m = re.search(r"label=\\textbf\{([^{}]*)\}", opts)
            label_fmt = label_m.group(1) if label_m else (
                opts if "alph" in opts else None
            )
            add_list(doc, m.group(3), kind, label_fmt)
            tex = tex[m.end():]
            continue

        # bibliography
        m = re.match(r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}",
                     tex, re.S)
        if m:
            add_banner(doc, "References", None)
            body = m.group(1)
            for bm in re.finditer(r"\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem|\Z)",
                                  body, re.S):
                key, entry = bm.group(1), bm.group(2).strip()
                entry = re.sub(r"\\newblock\s*", " ", entry)
                entry = re.sub(r"\\emph\{([^{}]*)\}", r"\1", entry)
                entry = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", entry)
                entry = re.sub(r"\\[a-zA-Z]+", " ", entry)
                entry = re.sub(r"\s+", " ", entry).strip()
                handle_stream.bib = getattr(handle_stream, "bib", 0) + 1
                p = doc.add_paragraph()
                para_spacing(p, 1, 3, 12.5)
                p.paragraph_format.left_indent = Mm(8)
                p.paragraph_format.first_line_indent = Mm(-8)
                r = p.add_run(f"[{handle_stream.bib}] ")
                set_run_font(r, FONT, 9.5, True)
                add_rich_text(p, entry, size=9.5)
            tex = tex[m.end():]
            continue

        # abstract via fcolorbox parbox
        m = re.match(
            r"\\fcolorbox\{[^{}]*\}\{[^{}]*\}\{\\parbox[^{]*\{[^{}]*\}\{%?(.*?)\}\}\}?",
            tex, re.S,
        )
        if m and "Abstract" in m.group(1)[:80]:
            add_box(doc, m.group(1), "FFFFFF", SIC_RULE, None)
            # lead "Abstract." already in body with color; ok
            tex = tex[m.end():]
            continue

        # paragraph: read until blank-line-ish / next command
        # stop at next top-level command
        stop = re.search(
            r"\n\s*(\\section|\\subsection|\\begin\{|\\finding\{|\\lead\{|\\bibitem)",
            tex,
        )
        if stop:
            para = tex[:stop.start()]
            tex = tex[stop.start():]
        else:
            para = tex
            tex = ""
        para = para.strip()
        if not para or para.startswith("\\"):
            # maybe \lead starting
            if para.startswith("\\lead"):
                pass
            else:
                if para:
                    # swallow unknown one-liners
                    nl = para.find("\n")
                    tex = para[nl + 1:] if nl >= 0 else ""
                continue
        # collapse
        para = re.sub(r"\s+", " ", para).strip()
        if para:
            add_body_para(doc, para)


def setup_doc() -> Document:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Mm(210)
    sec.page_height = Mm(297)
    sec.top_margin = Mm(30)
    sec.bottom_margin = Mm(25.4)
    sec.left_margin = Mm(25.4)
    sec.right_margin = Mm(25.4)
    sec.footer_distance = Mm(14.5)

    # Normal style
    style = doc.styles["Normal"]
    style.font.name = FONT
    style.font.size = Pt(10.5)
    style.font.color.rgb = RGBColor.from_string(BODY)
    rPr = style.element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.insert(0, rFonts)
    for a in ("w:ascii", "w:hAnsi", "w:cs"):
        rFonts.set(qn(a), FONT)

    # footer Page N / M
    footer = sec.footer
    fp = footer.paragraphs[0]
    fp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    para_spacing(fp, 0, 0, 12)
    r = fp.add_run("Page ")
    set_run_font(r, FONT, 10)
    add_field(fp, " PAGE ")
    r = fp.add_run(" / ")
    set_run_font(r, FONT, 10)
    add_field(fp, " NUMPAGES ")
    return doc


def add_cover(doc):
    # page 1: cover image
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    cover = HERE / "cover1.png"
    if cover.exists():
        run.add_picture(str(cover), width=Mm(210), height=Mm(297))
    # page break
    doc.add_page_break()

    # page 2: title block
    # title box
    table = doc.add_table(rows=1, cols=1)
    cell = table.rows[0].cells[0]
    tcPr = cell._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), "4")
        el.set(qn("w:color"), SIC_RULE)
        borders.append(el)
    tcPr.append(borders)
    tr = table.rows[0]
    tr.height = Mm(30.7)
    tr.height_rule = WD_ROW_HEIGHT_RULE.EXACTLY
    tp = cell.paragraphs[0]
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_spacing(tp, 6, 2, 22)
    r = tp.add_run("Bayan: On-Device Arabic Text Simplification\nfor Readers with Dyslexia")
    set_run_font(r, FONT, 20, True)
    tp2 = cell.add_paragraph()
    tp2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_spacing(tp2, 2, 2, 14)
    r = tp2.add_run("تبسيط")
    set_run_font(r, ARABIC_FONT, 12, False, False, BODY, rtl=True)
    r = tp2.add_run("  ·  Simplify")
    set_run_font(r, FONT, 12)

    # spacer to date at ~112mm from top
    for _ in range(6):
        sp = doc.add_paragraph()
        para_spacing(sp, 0, 8, 18)

    dp = doc.add_paragraph()
    dp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_spacing(dp, 0, 24, 22)
    r = dp.add_run("05/10/26")
    set_run_font(r, FONT, 18, True)

    for _ in range(4):
        sp = doc.add_paragraph()
        para_spacing(sp, 0, 6, 16)

    tp3 = doc.add_paragraph()
    tp3.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    para_spacing(tp3, 0, 2, 28)
    r = tp3.add_run("Cogni")
    set_run_font(r, FONT, 24, True)

    members = [
        "Marwan Elamami", "Abdulrahman Khengari", "Ahmed Alaeb",
        "Sanad Ali", "Mohammed Thabet", "Abdul Majid Mraied",
    ]
    for name in members:
        mp = doc.add_paragraph()
        mp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        para_spacing(mp, 0, 1, 14.6)
        r = mp.add_run(name)
        set_run_font(r, FONT, 12, True)

    doc.add_page_break()


def add_toc(doc):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    para_spacing(p, 8, 10, 28)
    r = p.add_run("Content")
    set_run_font(r, FONT, 24, True, False, SIC_BLUE)

    toc = [
        (1, "1. Introduction"),
        (2, "1.1. Background Information"),
        (2, "1.2. Motivation and Objective"),
        (2, "1.3. Members and Role Assignments"),
        (2, "1.4. Schedule and Milestones"),
        (2, "1.5. Related Work"),
        (1, "2. Project Execution"),
        (2, "2.1. Data Acquisition"),
        (2, "2.2. Training Methodology"),
        (2, "2.3. Workflow"),
        (2, "2.4. System Design"),
        (2, "2.5. BayanBench"),
        (2, "2.6. Human Rating Protocol"),
        (2, "2.7. The Meaning Judge"),
        (1, "3. Results"),
        (2, "3.1. Data Preprocessing"),
        (2, "3.2. Exploratory Data Analysis (EDA)"),
        (2, "3.3. Modeling"),
        (2, "3.4. Human Evaluation"),
        (2, "3.5. BayanBench Results"),
        (2, "3.6. User Interface"),
        (2, "3.7. Testing and Improvements"),
        (2, "3.8. On the Device"),
        (1, "4. Projected Impact"),
        (2, "4.1. Accomplishments and Benefits"),
        (2, "4.2. Future Improvements"),
        (2, "4.3. Limitations"),
        (2, "4.4. Conclusion"),
        (2, "References"),
    ]
    for lvl, title in toc:
        p = doc.add_paragraph()
        para_spacing(p, 2, 3, 13)
        p.paragraph_format.left_indent = Mm(5 if lvl == 2 else 0)
        r = p.add_run(title)
        set_run_font(r, FONT, 12 if lvl == 1 else 11, lvl == 1)

    # sections 5-6 appear on next TOC page in PDF
    for title in ("5. Team Member Review and Comment",
                  "6. Instructor Review and Comment"):
        p = doc.add_paragraph()
        para_spacing(p, 8, 3, 13)
        r = p.add_run(title)
        set_run_font(r, FONT, 12, True)
    doc.add_page_break()


def add_team_review(doc):
    add_banner(doc, "Team Member Review and Comment", "5")
    body = (
        "Each member reviews the work of the team and of themselves, "
        "commenting on what went well and what should be improved."
    )
    # pull the real table body from main.tex if present
    main = (LATEX / "main.tex").read_text(encoding="utf-8")
    m = re.search(
        r"5\.\s*Team Member Review.*?\\begin\{tabularx\}.*?\\end\{tabularx\}",
        main, re.S,
    )
    if m:
        tb = re.search(
            r"\\begin\{tabularx\}\s*\{[^{}]*\}\s*\{[^{}]*\}(.*?)\\end\{tabularx\}",
            m.group(0), re.S,
        )
        if tb:
            add_table(doc, tb.group(1), None, None)
            return
    add_body_para(doc, body)


def add_instructor_review(doc):
    add_banner(doc, "Instructor Review and Comment", "6")
    main = (LATEX / "main.tex").read_text(encoding="utf-8")
    m = re.search(
        r"\\begin\{tabularx\}\s*\{[^{}]*\}\s*\{[^{}]*\}(.*?)\\end\{tabularx\}",
        main[main.find("Instructor Review"):],
        re.S,
    )
    if m:
        add_table(doc, m.group(1), None, None)
    else:
        cats = [
            ("IDEA", "10"), ("APPLICATION", "30"), ("RESULT", "30"),
            ("PROJECT MANAGEMENT", "10"), ("PRESENTATION & REPORT", "20"),
            ("TOTAL", "100"),
        ]
        table = doc.add_table(rows=1, cols=3)
        hdr = table.rows[0].cells
        for i, t in enumerate(("CATEGORY", "SCORE", "REVIEW and COMMENT")):
            p = hdr[i].paragraphs[0]
            para_spacing(p, 1, 1, 12)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(t)
            set_run_font(r, FONT, 11, True)
            shade(hdr[i]._tc.get_or_add_tcPr(), SIC_HEAD)
            set_cell_borders(hdr[i])
        for cat, mx in cats:
            row = table.add_row()
            for i, t in enumerate((cat, f"__/{mx}", "")):
                p = row.cells[i].paragraphs[0]
                para_spacing(p, 1, 1, 12)
                r = p.add_run(t)
                set_run_font(r, FONT, 11, True)
                set_cell_borders(row.cells[i])


def extract_body_source() -> str:
    main = (LATEX / "main.tex").read_text(encoding="utf-8")
    main = strip_comments(main)
    # body after \begin{document}, without cover/toc
    m = re.search(r"\\begin\{document\}(.*)$", main, re.S)
    body = m.group(1) if m else main
    # remove siccover and siccontents invocations
    body = re.sub(r"\\siccover\s*\{.*?\}\s*\{.*?\}\s*\{.*?\}\s*\{.*?\}",
                  "", body, flags=re.S)
    body = body.replace("\\siccontents", "")
    # drop team/instructor sections — handled separately
    body = re.split(r"\\section\{Team Member Review", body)[0]
    # also drop trailing instructor if any
    return body


def main():
    load_macros()
    print(f"macros={len(MACROS)}")
    doc = setup_doc()
    handle_stream.sec = 0
    handle_stream.sub = 0
    handle_stream.figi = 0
    handle_stream.bib = 0

    add_cover(doc)
    add_toc(doc)
    add_body_para  # keep

    source = extract_body_source()
    print(f"body_source_chars={len(source)}")
    handle_stream(doc, source)

    add_team_review(doc)
    add_instructor_review(doc)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print("wrote", OUT, "tables_seq", TABLE_SEQ, "figures_seq", FIGURE_SEQ,
          "bib", handle_stream.bib)


if __name__ == "__main__":
    sys.exit(main())
