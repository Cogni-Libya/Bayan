#!/usr/bin/env python3
"""Build Bayan_Final_Report.docx from the SIC template OOXML + LaTeX content.

Reuses the template's embedded fonts, cover, footer, banner DrawingML shapes,
and review tables. Body text/tables/figures come from main.tex (+ generated
macros). Figures are PNG crops of the LaTeX PDF.
"""
from __future__ import annotations

import copy
import re
import shutil
import zipfile
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
LATEX = HERE.parent
DELIV = LATEX.parent
TEMPLATE = DELIV / "SIC_AI_Capstone Project_Final Report.docx"
OUT = DELIV / "Bayan_Final_Report.docx"
FIGS = HERE / "figs"

NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wps": "http://schemas.microsoft.com/office/word/2010/wordprocessingShape",
    "pic": "http://schemas.openxmlformats.org/drawingml/2006/picture",
}
W = "{%s}" % NS["w"]
R = "{%s}" % NS["r"]
WP = "{%s}" % NS["wp"]
A = "{%s}" % NS["a"]

SIC_BLUE = "193DB0"
SIC_HEAD = "DEE5FA"
SIC_RULE = "BFBFBF"
SIC_PALE = "EEF2FC"
BODY_COLOR = "000000"
FONT = "SamsungOne-400"
FONT_B = "SamsungOne-700"
SHARP = "Samsung Sharp Sans"
MONO = "Liberation Mono"
ARABIC = "PakType Naskh Basic"

MACROS: dict[str, str] = {}
FIG_SEQ = 0
TAB_SEQ = 0
BIB_SEQ = 0
SEC_NO = 0
SUB_NO = 0


# ------------------------------------------------------------------ macros
def load_macros() -> None:
    files = [
        "figures.tex", "results.tex", "bench_v2.tex", "human.tex",
        "model3.tex", "human_m3.tex", "main.tex",
    ]
    for name in files:
        text = (LATEX / name).read_text(encoding="utf-8")
        pos = 0
        key = "\\newcommand{\\"
        while True:
            i = text.find(key, pos)
            if i < 0:
                break
            j = i + len(key)
            k = text.find("}", j)
            macro = text[j:k]
            # optional [n] args skip
            if k + 1 < len(text) and text[k + 1] == "[":
                # skip optional args
                k = text.find("]", k + 1)
            if k + 1 >= len(text) or text[k + 1] != "{":
                pos = k + 1
                continue
            # brace match body
            start = k + 1
            depth = 0
            m = start
            while m < len(text):
                if text[m] == "{":
                    depth += 1
                elif text[m] == "}":
                    depth -= 1
                    if depth == 0:
                        MACROS[macro] = text[start + 1:m]
                        break
                m += 1
            pos = m + 1 if m < len(text) else len(text)
    # explicit model names
    MACROS.setdefault("vOne", "BayanSimplify-v0.1")
    MACROS.setdefault("vTwo", "BayanSimplify-v0.2")
    MACROS.setdefault("vTwoFast", "BayanSimplify-v0.2-Fast")
    MACROS.setdefault("vThree", "BayanSimplify-v0.3")
    MACROS.setdefault("textminus", "−")


STRUCTURAL = {
    "section", "subsection", "lead", "ar", "textbf", "emph", "texttt", "textit",
    "cite", "autoref", "item", "caption", "label", "includegraphics", "finding",
    "footnote", "input", "bibitem", "makecell", "head", "multicolumn",
    "cellcolor", "hline", "resizebox", "hspace", "vspace", "noindent", "small",
    "scriptsize", "footnotesize", "tiny", "centering", "center", "fcolorbox",
    "parbox", "dimexpr", "linewidth", "enspace", "begin", "end", "mbox",
    "mathrm", "hat", "alpha", "geq", "leq", "times", "approx", "cdot",
    "newcommand", "done", "wip", "todo",
    "cat", "score", "siccover", "siccontents", "addcontentsline", "clearpage",
    "null", "thispagestyle", "setlength", "setcounter", "renewcommand",
    "pagestyle", "fancyhf", "fancyfoot", "textwidth", "thebibliography",
    "endthebibliography", "textminus", "member", "bibliography",
    "resultstable", "barectable", "figsari", "figbehaviour", "benchheadtable",
    "benchothertable", "benchsettable", "benchsetstable", "benchefftable",
    "scoreraucatable", "humansystable", "readertable", "pairstable",
    "figschedule", "figevolution", "figpipeline", "figarchitecture",
    "figcleaning", "figlengths", "figtraining", "figtrainingtwo", "figui",
    "figtradeoff", "figscorer", "figdumbbell",
}


def expand(text: str) -> str:
    for name, val in MACROS.items():
        if name in STRUCTURAL:
            continue
        # consume optional empty {} after parameterless macros (\vOne{} → value)
        text = re.sub(
            r"\\" + re.escape(name) + r"(?![A-Za-z@])\s*(\{\})?",
            lambda m, _v=val: _v,
            text,
        )
    return text


def strip_comments(tex: str) -> str:
    # keep escaped \% ; only strip real comments
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in tex.splitlines())


CITE_ORDER: dict[str, int] = {}
AUTOREF: dict[str, str] = {}


def build_cite_order(tex: str) -> None:
    CITE_ORDER.clear()
    m = re.search(r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}", tex, re.S)
    if not m:
        return
    n = 0
    for bm in re.finditer(r"\\bibitem\{([^}]*)\}", m.group(1)):
        n += 1
        for key in bm.group(1).split(","):
            CITE_ORDER[key.strip()] = n


def build_autoref_map(tex: str) -> None:
    """Map \\label{...} → human autoref text used in the PDF."""
    AUTOREF.clear()
    sec = sub = tab = fig = 0
    # walk the document in order for numbering
    pos = 0
    pat = re.compile(
        r"\\section\*?\{[^{}]*\}"
        r"|\\subsection\*?\{[^{}]*\}"
        r"|\\caption\{"
        r"|\\label\{([^}]*)\}"
        r"|\\begin\{figure\}"
        r"|\\begin\{table\}"
    )
    last_caption_kind = None
    for m in pat.finditer(tex):
        tok = m.group(0)
        if tok.startswith("\\section") and not tok.startswith("\\section*"):
            sec += 1
            sub = 0
            last_caption_kind = None
        elif tok.startswith("\\subsection"):
            sub += 1
            last_caption_kind = None
        elif tok.startswith("\\begin{figure}"):
            last_caption_kind = "fig"
        elif tok.startswith("\\begin{table}"):
            last_caption_kind = "tab"
        elif tok.startswith("\\caption{"):
            if last_caption_kind == "fig":
                fig += 1
            elif last_caption_kind == "tab":
                tab += 1
        elif tok.startswith("\\label{"):
            label = m.group(1)
            if label.startswith("sec:"):
                if sub and not label.endswith("glance"):
                    AUTOREF[label] = f"subsection {sec}.{sub}" if sec else f"section {sec}"
                else:
                    AUTOREF[label] = f"section {sec}"
            elif label.startswith("tab:"):
                AUTOREF[label] = f"Table {tab}"
            elif label.startswith("fig:"):
                AUTOREF[label] = f"Figure {fig}"
            else:
                AUTOREF[label] = label


# ------------------------------------------------------------------ XML utils
def el(tag: str, **attrs):
    e = etree.Element(W + tag)
    for k, v in attrs.items():
        e.set(W + k, str(v))
    return e


def run(text: str, *, font=FONT, size=21, bold=False, italic=False,
        color=BODY_COLOR, rtl=False) -> etree.Element:
    """size in half-points."""
    r = el("r")
    rPr = el("rPr")
    fonts = el("rFonts")
    fonts.set(W + "ascii", font)
    fonts.set(W + "hAnsi", font)
    fonts.set(W + "cs", ARABIC if rtl else "Times New Roman")
    rPr.append(fonts)
    if bold:
        rPr.append(el("b"))
        rPr.append(el("bCs"))
    if italic:
        rPr.append(el("i"))
        rPr.append(el("iCs"))
    if color and color != BODY_COLOR:
        c = el("color")
        c.set(W + "val", color)
        rPr.append(c)
    for tag in ("sz", "szCs"):
        s = el(tag)
        s.set(W + "val", str(size))
        rPr.append(s)
    if rtl:
        lang = el("lang")
        lang.set(W + "val", "ar-SA")
        lang.set(W + "bidi", "ar-SA")
        rPr.append(lang)
        rPr.append(el("rtl"))
        rPr.append(el("rtlCs"))
    r.append(rPr)
    # last-ditch cleanup of TeX crumbs
    text = text.replace("\\rightarrow", "→").replace("\\leftarrow", "←")
    text = text.replace("\\dagger", "†").replace("\\to", "→")
    text = text.replace("^*", "∗")
    text = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    t = el("t")
    t.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    t.text = text
    r.append(t)
    return r


def paragraph(*runs, align=None, before=0, after=100, line=284, line_rule="exact",
              left=0, hanging=0, page_break_before=False) -> etree.Element:
    p = el("p")
    pPr = el("pPr")
    if page_break_before:
        pPr.append(el("pageBreakBefore"))
    spacing = el("spacing")
    spacing.set(W + "before", str(before))
    spacing.set(W + "after", str(after))
    if line_rule == "auto" and line is None:
        pass  # default single spacing
    elif line_rule == "auto":
        spacing.set(W + "line", str(line))
        spacing.set(W + "lineRule", "auto")
    else:
        spacing.set(W + "line", str(line))
        spacing.set(W + "lineRule", line_rule)
    pPr.append(spacing)
    if left or hanging:
        ind = el("ind")
        if left:
            ind.set(W + "left", str(left))
        if hanging:
            ind.set(W + "hanging", str(hanging))
        pPr.append(ind)
    if align:
        jc = el("jc")
        jc.set(W + "val", align)
        pPr.append(jc)
    p.append(pPr)
    for r in runs:
        p.append(r)
    return p


def page_break() -> etree.Element:
    p = el("p")
    r = el("r")
    br = el("br")
    br.set(W + "type", "page")
    r.append(br)
    p.append(r)
    return p


def set_cell_shading(tc, fill: str):
    tcPr = tc.find(W + "tcPr")
    if tcPr is None:
        tcPr = el("tcPr")
        tc.insert(0, tcPr)
    shd = el("shd")
    shd.set(W + "val", "clear")
    shd.set(W + "color", "auto")
    shd.set(W + "fill", fill)
    tcPr.append(shd)


def set_tc_width(tc, dxa: int):
    tcPr = tc.find(W + "tcPr")
    if tcPr is None:
        tcPr = el("tcPr")
        tc.insert(0, tcPr)
    tcW = el("tcW")
    tcW.set(W + "w", str(dxa))
    tcW.set(W + "type", "dxa")
    tcPr.append(tcW)


def set_tc_borders(tc, color=SIC_RULE, sz="4"):
    tcPr = tc.find(W + "tcPr")
    if tcPr is None:
        tcPr = el("tcPr")
        tc.insert(0, tcPr)
    borders = el("tcBorders")
    for edge in ("top", "left", "bottom", "right"):
        b = el(edge)
        b.set(W + "val", "single")
        b.set(W + "sz", sz)
        b.set(W + "color", color)
        borders.append(b)
    tcPr.append(borders)


def make_table(rows_of_cells, col_dxa=None, header_rows=1, band_rows=None):
    """rows_of_cells: list of list of paragraph elements (or list of runs)."""
    band_rows = set(band_rows or [])
    tbl = el("tbl")
    tblPr = el("tblPr")
    tblW = el("tblW")
    tblW.set(W + "w", "9010")
    tblW.set(W + "type", "dxa")
    tblPr.append(tblW)
    layout = el("tblLayout")
    layout.set(W + "type", "fixed")
    tblPr.append(layout)
    borders = el("tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b = el(edge)
        b.set(W + "val", "single")
        b.set(W + "sz", "4")
        b.set(W + "color", SIC_RULE)
        borders.append(b)
    tblPr.append(borders)
    tbl.append(tblPr)

    ncols = max(len(r) for r in rows_of_cells) if rows_of_cells else 1
    if not col_dxa:
        col_dxa = [9010 // ncols] * ncols
        col_dxa[-1] += 9010 - sum(col_dxa)
    grid = el("tblGrid")
    for w in col_dxa:
        gc = el("gridCol")
        gc.set(W + "w", str(w))
        grid.append(gc)
    tbl.append(grid)

    for ri, cells in enumerate(rows_of_cells):
        tr = el("tr")
        # band = explicitly marked multicolumn/header band only
        if ri in band_rows:
            tc = el("tc")
            tcPr = el("tcPr")
            span = el("gridSpan")
            span.set(W + "val", str(ncols))
            tcPr.append(span)
            tc.append(tcPr)
            set_cell_shading(tc, SIC_HEAD)
            set_tc_borders(tc)
            content = cells[0]
            if isinstance(content, etree.Element):
                tc.append(content)
            else:
                tc.append(paragraph(*content, after=20, line=240))
            tr.append(tc)
            tbl.append(tr)
            continue
        for ci in range(ncols):
            tc = el("tc")
            set_tc_width(tc, col_dxa[ci] if ci < len(col_dxa) else 2000)
            set_tc_borders(tc)
            if ri < header_rows:
                set_cell_shading(tc, SIC_HEAD)
            content = cells[ci] if ci < len(cells) else ""
            if isinstance(content, etree.Element):
                tc.append(content)
            elif isinstance(content, list):
                tc.append(paragraph(*content, after=20, line=240))
            else:
                tc.append(paragraph(run(str(content), size=18, bold=ri < header_rows),
                                    after=20, line=240))
            tr.append(tc)
        tbl.append(tr)
    return tbl


# ------------------------------------------------------------------ rich text
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
    r"|(?P<plain>[^\\$]+)",
)

PLAIN_MAP = [
    ("\\%", "%"), ("\\&", "&"), ("\\#", "#"), ("\\_", "_"),
    ("\\-", ""),  # discretionary hyphen
    ("\\enspace", " "), ("\\,", " "), ("\\;", " "),
    ("---", "—"), ("--", "–"),
    ("``", "“"), ("''", "”"),
    ("~", " "),
]


def flatten(s: str) -> str:
    for a, b in PLAIN_MAP:
        s = s.replace(a, b)
    return s


def _read_cmd(text: str, i: int):
    """If text[i] is \\cmd{arg}, return (cmd, arg, end). Else None."""
    if i >= len(text) or text[i] != "\\":
        return None
    j = i + 1
    if j < len(text) and text[j].isalpha():
        k = j
        while k < len(text) and text[k].isalpha():
            k += 1
        cmd = text[j:k]
    elif j < len(text) and text[j] in "$%&#_~":
        return (text[j], text[j], j + 1)
    else:
        return None
    p = k
    while p < len(text) and text[p] in " \n\t":
        p += 1
    if p < len(text) and text[p] == "{":
        arg, end = grab_braced(text, p)
        return cmd, arg, end
    return cmd, None, k


def rich_runs(text: str, size=21, bold=False, italic=False, color=BODY_COLOR) -> list:
    """Scanner-based rich text (handles nested braces)."""
    text = re.sub(r"(?<!\\)%.*", "", text)
    text = re.sub(r"\\color\{[^{}]*\}", "", text)
    text = re.sub(r"\\textcolor\{[^{}]*\}\{([^{}]*)\}", r"\1", text)
    text = text.replace("\\%", "%").replace("\\&", "&").replace("\\#", "#").replace("\\_", "_")
    text = text.replace("\\-", "")
    text = re.sub(r"\\[=`'\"^~.]\s*\{?([A-Za-z])\}?", r"\1", text)
    text = re.sub(r"\\[dHctvb]\{([A-Za-z])\}", r"\1", text)
    out = []
    i = 0
    n = len(text)
    plain = []

    def flush():
        if plain:
            s = flatten("".join(plain))
            plain.clear()
            if s:
                out.append(run(s, size=size, bold=bold, italic=italic, color=color))

    while i < n:
        ch = text[i]
        if ch == "^" and i + 1 < n and text[i+1] == "{":
            inner, end = grab_braced(text, i + 1)
            flush()
            out.append(run(inner, size=size - 2, bold=bold, italic=True, color=color))
            i = end
            continue
        if ch == "_" and i + 1 < n and text[i+1] == "{":
            inner, end = grab_braced(text, i + 1)
            flush()
            out.append(run(inner, size=size - 2, bold=bold, italic=True, color=color))
            i = end
            continue
        if ch == "$":
            j = text.find("$", i + 1)
            if j < 0:
                plain.append(ch); i += 1; continue
            flush()
            inner = text[i+1:j]
            for a, b in [
                ("\\times", "×"), ("\\geq", "≥"), ("\\ge", "≥"),
                ("\\approx", "≈"), ("\\alpha", "α"), ("\\hat y", "ŷ"),
                ("\\oplus", "⊕"), ("\\leq", "≤"), ("\\le", "≤"),
                ("\\cdot", "·"),
            ]:
                inner = inner.replace(a, b)
            out.append(run(inner, size=size, bold=bold, italic=True, color=color))
            i = j + 1
            continue
        if ch == "\\":
            parsed = _read_cmd(text, i)
            if not parsed:
                plain.append(ch); i += 1; continue
            cmd, arg, end = parsed
            if cmd == "ar" and arg is not None:
                flush()
                out.append(run(arg, font=ARABIC, size=size, bold=bold,
                               italic=italic, color=color, rtl=True))
            elif cmd == "lead" and arg is not None:
                flush()
                out.append(run(arg + " ", size=size, bold=True, color=color))
            elif cmd == "textbf" and arg is not None:
                flush()
                out.extend(rich_runs(arg, size, True, italic, color))
            elif cmd in ("emph", "textit") and arg is not None:
                flush()
                out.extend(rich_runs(arg, size, bold, True, color))
            elif cmd == "texttt" and arg is not None:
                flush()
                sub = rich_runs(arg, size - 1, bold, italic, color)
                for r in sub:
                    fonts = r.find(W + "rPr").find(W + "rFonts")
                    fonts.set(W + "ascii", MONO)
                    fonts.set(W + "hAnsi", MONO)
                out.extend(sub)
            elif cmd == "cite" and arg is not None:
                flush()
                nums = [str(CITE_ORDER.get(k.strip(), k.strip())) for k in arg.split(",")]
                out.append(run("[" + ", ".join(nums) + "]", size=size, bold=bold, color=color))
            elif cmd == "autoref" and arg is not None:
                flush()
                out.append(run(AUTOREF.get(arg, arg), size=size, bold=bold, color=color))
            elif cmd == "footnote":
                flush()
                out.append(run("†", size=size - 2, bold=bold, color=color))
            elif cmd in ("enspace", ",", ";", "!", "quad", "qquad"):
                plain.append(" ")
            elif cmd in ("%", "&", "#", "_", "~"):
                plain.append(cmd)
            elif cmd in ("textminus",):
                plain.append("−")
            elif cmd == "dagger":
                plain.append("†")
            elif cmd == "rightarrow":
                plain.append("→")
            elif cmd == "leftarrow":
                plain.append("←")
            elif cmd == "to":
                plain.append("→")
            elif cmd in ("hat", "bar", "tilde", "vec") and arg:
                plain.append(arg)
            elif cmd in ("rightarrow", "to", "dagger", "leftarrow"):
                plain.append({
                    "rightarrow": "→", "to": "→",
                    "dagger": "†", "leftarrow": "←",
                }[cmd])
            elif cmd == "leftarrow":
                plain.append("←")
            elif cmd == "mbox" and arg is not None:
                flush()
                out.extend(rich_runs(arg, size, bold, italic, color))
            elif cmd in ("vOne", "vTwo", "vTwoFast", "vThree"):
                plain.append(MACROS.get(cmd, cmd))
            else:
                # unknown command: keep arg text if any, drop the command
                if arg is not None:
                    plain.append(arg)
            i = end
            continue
        plain.append(ch)
        i += 1
    flush()
    return out

def expand_structural_macros(tex: str) -> str:
    for name in (
        "resultstable", "barectable", "benchheadtable", "benchothertable",
        "benchsetstable", "benchefftable", "scoreraucatable", "humansystable",
        "readertable", "pairstable",
        "figsari", "figbehaviour", "figschedule", "figevolution", "figpipeline",
        "figarchitecture", "figcleaning", "figlengths", "figtraining",
        "figtrainingtwo", "figui", "figtradeoff", "figscorer", "figdumbbell",
    ):
        if name in MACROS:
            val = MACROS[name]
            tex = re.sub(
                r"\\" + name + r"(?![A-Za-z@])",
                lambda m, _v=val: _v,
                tex,
            )
    return tex


def parse_cells(line: str) -> list[str]:
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
    return cells


def clean_cell(text: str, size=18) -> list:
    is_head = "\\head{" in text
    t = text
    # brace-aware \head{...}
    while "\\head{" in t:
        i = t.find("\\head{")
        inner, end = grab_braced(t, i + 5)
        t = t[:i] + "{" + inner + "}" + t[end:]
    # strip \multicolumn{n}{spec}{...} → third arg
    while "\\multicolumn" in t:
        i = t.find("\\multicolumn")
        j = i + len("\\multicolumn")
        for _ in range(2):
            while j < len(t) and t[j] in " \n\t":
                j += 1
            if j < len(t) and t[j] == "{":
                j = match_braced(t, j)
        while j < len(t) and t[j] in " \n\t":
            j += 1
        if j < len(t) and t[j] == "{":
            inner, end = grab_braced(t, j)
            t = t[:i] + "{" + inner + "}" + t[end:]
        else:
            t = t[:i] + t[j:]
    t = t.replace("\\cellcolor{sichead}", "")
    t = t.replace("\\centering", "").replace("\\arraybackslash", "")
    t = t.replace("\\bfseries", "")
    # \makecell{...} brace-aware → stacked lines (as in the LaTeX PDF)
    makecell_parts = None
    while "\\makecell{" in t:
        i = t.find("\\makecell{")
        inner, end = grab_braced(t, i + 9)
        inner = re.sub(r"\\tiny|\\small|\\scriptsize|\\footnotesize", "", inner)
        inner = re.sub(r"\[-\d+(?:\.\d+)?pt\]", "", inner)
        inner = inner.replace("\\%", "%").replace("\\-", "")
        while True:
            m = re.search(r"\{([^{}]*)\}", inner)
            if not m:
                break
            inner = inner[:m.start()] + m.group(1) + inner[m.end():]
        parts = [re.sub(r"\s+", " ", p).strip(" {}") for p in inner.split("\\\\")]
        parts = [p for p in parts if p]
        t = t[:i] + " ".join(parts) + t[end:]
        makecell_parts = parts
    t = re.sub(r"\[-\d+(?:\.\d+)?pt\]", "", t)
    # unwrap orphan braces only — never \cmd{...} (those must reach rich_runs)
    out = []
    i = 0
    while i < len(t):
        if t[i] == "\\" and i + 1 < len(t):
            j = i + 1
            while j < len(t) and t[j].isalpha():
                j += 1
            k = j
            while k < len(t) and t[k] in " \t":
                k += 1
            if k < len(t) and t[k] == "{":
                end = match_braced(t, k)
                out.append(t[i:end])
                i = end
                continue
            out.append(t[i:j])
            i = j
            continue
        if t[i] == "{":
            end = match_braced(t, i)
            if end > i:
                out.append(t[i + 1:end - 1])
                i = end
                continue
            i += 1
            continue
        out.append(t[i])
        i += 1
    t = "".join(out)
    t = t.replace("^*", "∗")
    if makecell_parts and len(makecell_parts) >= 2:
        runs_ = rich_runs(makecell_parts[0], size=size, bold=is_head)
        br_run = el("r")
        br_run.append(el("br"))
        runs_.append(br_run)
        runs_.extend(rich_runs(" ".join(makecell_parts[1:]), size=size - 1, bold=is_head))
        return runs_
    runs_ = rich_runs(t, size=size, bold=is_head)
    return runs_


def match_braced(s: str, start: int) -> int:
    """Return index after the {...} group starting at s[start]=='{'."""
    if start >= len(s) or s[start] != "{":
        return -1
    depth = 0
    i = start
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return -1


def grab_braced(s: str, start: int) -> tuple[str, int]:
    """Grab {...} starting at s[start]=='{'. Returns (inner, end_index)."""
    end = match_braced(s, start)
    if end < 0:
        return "", start
    return s[start + 1:end - 1], end


def parse_tabular(body: str):
    body = body.lstrip()
    if body.startswith("{"):
        end = match_braced(body, 0)
        if end > 0:
            body = body[end:]
    # drop hline markers only (do NOT turn source newlines into row breaks)
    body = re.sub(r"\\hline|\\toprule|\\midrule|\\bottomrule", " ", body)
    # split rows on \\ only outside braces (keep \makecell{a\\b} intact)
    parts = []
    depth = 0
    cur = []
    i = 0
    while i < len(body):
        if body[i] == "{":
            depth += 1
            cur.append(body[i]); i += 1
        elif body[i] == "}":
            depth -= 1
            cur.append(body[i]); i += 1
        elif depth == 0 and body.startswith("\\\\", i):
            j = i + 2
            if j < len(body) and body[j] == "[":
                k = body.find("]", j)
                j = k + 1 if k >= 0 else j
            parts.append("".join(cur))
            cur = []
            i = j
        else:
            cur.append(body[i]); i += 1
    if cur:
        parts.append("".join(cur))
    rows = []
    for raw in parts:
        line = raw.strip()
        if not line:
            continue
        cells = parse_cells(line)
        cells = [" ".join(c.split()) for c in cells]
        if any(cells):
            rows.append(cells)
    return rows


def match_tabular_env(tex: str):
    """Match \\begin{tabular[x]}{len}{spec} ... \\end{tabular[x]} at start of tex.
    Returns (spec, inner_body, end_index) or None.
    """
    m = re.match(r"\\begin\{(tabularx?)\}", tex)
    if not m:
        return None
    env = m.group(1)
    i = m.end()
    while i < len(tex) and tex[i] in " \t\n":
        i += 1
    # width arg
    if i < len(tex) and tex[i] == "{":
        i = match_braced(tex, i)
    while i < len(tex) and tex[i] in " \t\n":
        i += 1
    # spec arg
    if i < len(tex) and tex[i] != "{":
        return None
    spec_end = match_braced(tex, i)
    if spec_end < 0:
        return None
    spec = tex[i + 1:spec_end - 1]
    end_m = re.search(r"\\end\{" + env + r"\}", tex[spec_end:])
    if not end_m:
        return None
    inner = tex[spec_end:spec_end + end_m.start()]
    return spec, inner, spec_end + end_m.end()


def parse_column_widths(spec: str) -> list[int] | None:
    """Parse |p{27mm}|p{30mm}|L| into dxa widths. L/X flexible."""
    parts = re.findall(r"[pCLX]\{([^}]*)\}|([LX])", spec)
    widths = []
    flexible = False
    for group in spec.split("|"):
        g = group.strip()
        if not g:
            continue
        m = re.match(r"[pC]\{([^}]+)\}", g)
        if m:
            val = m.group(1)
            mm = re.match(r"([\d.]+)mm", val)
            if mm:
                widths.append(int(float(mm.group(1)) * 56.6929))
            else:
                widths.append(1800)
        else:
            flexible = True
            widths.append(1800)
    if not widths:
        return None
    if flexible:
        total = 9010
        fixed = sum(widths)
        nflex = sum(1 for g in spec.split("|") if g.strip() in ("L", "X"))
        if nflex and fixed < total:
            extra = (total - fixed) // nflex
            widths = [w if w != 1800 or False else w for w in widths]
            # assign extra to flexible cols
            idx = 0
            neww = []
            for g in spec.split("|"):
                g = g.strip()
                if not g:
                    continue
                if g in ("L", "X"):
                    neww.append(1800 + extra)
                else:
                    neww.append(widths[idx] if idx < len(widths) else 1800)
                idx += 1
            widths = neww
    # normalize to 9010
    s = sum(widths)
    if s > 0:
        widths = [int(w * 9010 / s) for w in widths]
        widths[-1] += 9010 - sum(widths)
    return widths


def emit_table(body: str, caption: str | None):
    global TAB_SEQ
    out = []
    if caption:
        TAB_SEQ += 1
        out.append(paragraph(
            run(f"Table {TAB_SEQ}. ", size=19, bold=True, color=SIC_BLUE),
            *rich_runs(caption, size=19),
            after=60, line=240,
        ))
    # body may be "{spec}inner" or just inner
    spec = ""
    raw = body.lstrip()
    if raw.startswith("{"):
        spec_end = match_braced(raw, 0)
        if spec_end > 0:
            spec = raw[1:spec_end - 1]
            raw = raw[spec_end:]
    rows = parse_tabular(raw)
    if not rows:
        return out
    col_dxa = parse_column_widths(spec)
    ncols = max(len(r) for r in rows)
    if col_dxa and len(col_dxa) < ncols:
        col_dxa = col_dxa + [9010 // ncols] * (ncols - len(col_dxa))
        col_dxa = col_dxa[:ncols]
        s = sum(col_dxa)
        col_dxa = [int(w * 9010 / s) for w in col_dxa]
        col_dxa[-1] += 9010 - sum(col_dxa)

    processed = []
    band_rows = []
    for i, cells in enumerate(rows):
        joined = " ".join(cells)
        # true category band: \multicolumn spanning the row
        if "\\multicolumn" in joined:
            band_rows.append(i)
            t = re.sub(r"\\multicolumn\{\d+\}\{[^{}]*\}", "", joined)
            t = t.replace("\\cellcolor{sichead}", "").replace("\\bfseries", "")
            t = t.replace("\\%", "%").replace("\\&", "&").replace("\\#", "#").replace("\\-", "")
            t = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", t)
            t = re.sub(r"\\[a-zA-Z]+", " ", t)
            t = t.replace("{", "").replace("}", "")
            processed.append([run(re.sub(r"\s+", " ", t).strip(), size=18, bold=True)])
            continue
        processed.append([clean_cell(c) for c in cells])
    out.append(make_table(processed, col_dxa, header_rows=1, band_rows=band_rows))
    return out


def emit_figure(caption: str, path: Path):
    global FIG_SEQ
    FIG_SEQ += 1
    out = []
    # image paragraph via python-docx-compatible drawing is heavy; use a
    # simple w:pict-less approach: DrawingML blip. We'll add via rel later.
    out.append(("IMAGE", str(path), caption))
    return out


# ------------------------------------------------------------------ document
def load_template_parts():
    zin = zipfile.ZipFile(TEMPLATE)
    doc_xml = zin.read("word/document.xml")
    return zin, doc_xml


def make_banner_drawing(docPr_id: int = 100):
    """Clone the template banner rectangle DrawingML."""
    # minimal recreation matching template metrics
    xml = f'''<w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
     xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
     xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
     xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
  <w:pPr><w:spacing w:before="220" w:after="160" w:line="240" w:lineRule="exact"/></w:pPr>
  <w:r>
    <w:drawing>
      <wp:anchor distT="0" distB="0" distL="114300" distR="114300" simplePos="0"
                 relativeHeight="251659264" behindDoc="1" locked="0"
                 layoutInCell="1" allowOverlap="1">
        <wp:simplePos x="0" y="0"/>
        <wp:positionH relativeFrom="column"><wp:posOffset>-8890</wp:posOffset></wp:positionH>
        <wp:positionV relativeFrom="paragraph"><wp:posOffset>-2400</wp:posOffset></wp:positionV>
        <wp:extent cx="5735955" cy="249555"/>
        <wp:effectExtent l="0" t="0" r="0" b="0"/>
        <wp:wrapNone/>
        <wp:docPr id="{docPr_id}" name="Banner{docPr_id}"/>
        <wp:cNvGraphicFramePr/>
        <a:graphic>
          <a:graphicData uri="http://schemas.microsoft.com/office/word/2010/wordprocessingShape">
            <wps:wsp>
              <wps:cNvSpPr/>
              <wps:spPr>
                <a:xfrm><a:off x="0" y="0"/><a:ext cx="5735955" cy="249555"/></a:xfrm>
                <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                <a:solidFill><a:srgbClr val="193DB0"/></a:solidFill>
                <a:ln><a:noFill/></a:ln>
              </wps:spPr>
              <wps:style>
                <a:lnRef idx="1"><a:schemeClr val="accent1"/></a:lnRef>
                <a:fillRef idx="3"><a:schemeClr val="accent1"/></a:fillRef>
                <a:effectRef idx="0"><a:schemeClr val="accent1"/></a:effectRef>
                <a:latinRef idx="minor"><a:schemeClr val="accent1"/></a:latinRef>
              </wps:style>
              <wps:txbx>
                <w:txbxContent>
                  <w:p>
                    <w:pPr>
                      <w:spacing w:before="0" w:after="0" w:line="280" w:lineRule="exact"/>
                      <w:ind w:left="142"/>
                    </w:pPr>
                    <w:r>
                      <w:rPr>
                        <w:rFonts w:ascii="SamsungOne-700" w:hAnsi="SamsungOne-700"/>
                        <w:b/><w:bCs/>
                        <w:color w:val="FFFFFF"/>
                        <w:sz w:val="28"/><w:szCs w:val="28"/>
                      </w:rPr>
                      <w:t>__TITLE__</w:t>
                    </w:r>
                  </w:p>
                </w:txbxContent>
              </wps:txbx>
              <wps:bodyPr anchor="ctr"/>
            </wps:wsp>
          </a:graphicData>
        </a:graphic>
      </wp:anchor>
    </w:drawing>
  </w:r>
</w:p>'''
    return xml


def banner_para(title: str, numbered: str | None, docPr_id: int) -> etree.Element:
    text = f"{numbered}. {title}" if numbered else title
    xml = make_banner_drawing(docPr_id)
    xml = xml.replace("__TITLE__", text.replace("&", "&amp;").replace("<", "&lt;"))
    # parse with ns
    p = etree.fromstring(xml.encode())
    return p


def add_image_para(p_el, path: Path, width_emu: int, height_emu: int):
    """Append a DrawingML inline image to paragraph."""
    rid = p_el.attrib.get("img-rid")
    drawing_xml = f'''<w:drawing xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
      xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
      xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
      xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
      xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
  <wp:inline distT="0" distB="0" distL="0" distR="0">
    <wp:extent cx="{width_emu}" cy="{height_emu}"/>
    <wp:effectExtent l="0" t="0" r="0" b="0"/>
    <wp:docPr id="1000" name="Figure"/>
    <wp:cNvGraphicFramePr>
      <a:graphicFrameLocks noChangeAspect="1"/>
    </wp:cNvGraphicFramePr>
    <a:graphic>
      <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <pic:pic>
          <pic:nvPicPr>
            <pic:cNvPr id="1000" name="fig"/>
            <pic:cNvPicPr/>
          </pic:nvPicPr>
          <pic:blipFill>
            <a:blip r:embed="{rid}"/>
            <a:stretch><a:fillRect/></a:stretch>
          </pic:blipFill>
          <pic:spPr>
            <a:xfrm>
              <a:off x="0" y="0"/>
              <a:ext cx="{width_emu}" cy="{height_emu}"/>
            </a:xfrm>
            <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
          </pic:spPr>
        </pic:pic>
      </a:graphicData>
    </a:graphic>
  </wp:inline>
</w:drawing>'''
    r = el("r")
    d = etree.fromstring(drawing_xml.encode())
    r.append(d)
    p_el.append(r)


def collect_body_nodes(tex: str) -> list:
    """Return list of body nodes (etree Elements or ('IMAGE', path, cap))."""
    tex = strip_comments(tex)
    tex = expand_structural_macros(tex)
    tex = expand(tex)
    build_autoref_map(tex)

    # cleanup
    tex = re.sub(r"\\label\{[^}]*\}", "", tex)
    tex = re.sub(r"\\begin\{document\}|\\end\{document\}", "", tex)
    tex = re.sub(r"\\begin\{fullwidth\}|\\end\{fullwidth\}", "", tex)
    tex = re.sub(
        r"\\clearpage|\\newpage|\\null|\\thispagestyle\{[^}]*\}",
        lambda m: "\n\\PAGEBREAK\\n",
        tex,
    )
    tex = re.sub(r"\\FloatBarrier|\\noindent", "", tex)
    tex = re.sub(r"\\vspace\*?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\hspace\*?\{[^}]*\}", "", tex)
    tex = re.sub(r"\\small|\\footnotesize|\\scriptsize|\\tiny", "", tex)
    tex = re.sub(r"\\centering", "", tex)
    tex = re.sub(r"\\begin\{center\}|\\end\{center\}", "", tex)

    nodes = []
    docPr = [200]

    def add_banner(title, numbered):
        docPr[0] += 1
        nodes.append(banner_para(title, numbered, docPr[0]))

    fig_idx = [0]
    fig_files = [
        "fig01_schedule", "fig02_evolution", "fig03_pipeline", "fig04_architecture",
        "fig05_cleaning", "fig06_lengths", "fig07_sari", "fig08_behaviour",
        "fig09_trainingtwo", "fig10_scorer", "fig11_tradeoff", "fig12_ui",
    ]

    while tex.strip():
        tex = tex.lstrip()
        if not tex:
            break
        if tex.startswith("\\PAGEBREAK"):
            nodes.append(page_break())
            tex = tex[len("\\PAGEBREAK"):].lstrip()
            continue

        m = re.match(r"\\section\*?\{([^{}]*)\}", tex)
        if m:
            title = m.group(1)
            if not m.group(0).startswith("\\section*"):
                globals()["SEC_NO"] = globals().get("SEC_NO", 0) + 1
                globals()["SUB_NO"] = 0
                add_banner(title, str(globals()["SEC_NO"]))
            else:
                add_banner(title, None)
            tex = tex[m.end():]
            continue

        m = re.match(r"\\subsection\*?\{([^{}]*)\}", tex)
        if m:
            title = m.group(1)
            globals()["SUB_NO"] = globals().get("SUB_NO", 0) + 1
            p = paragraph(
                run(f"{globals().get('SEC_NO', 0)}.{globals()['SUB_NO']}. ", size=22, bold=True),
                *rich_runs(title, size=22, bold=True),
                before=220, after=60, line=280,
            )
            nodes.append(p)
            tex = tex[m.end():]
            continue

        m = re.match(r"\\finding\{((?:[^{}]|\{[^{}]*\})*)\}", tex, re.S)
        if m:
            runs_ = rich_runs(m.group(1), size=21)
            tbl = make_table([[runs_]], [9010], header_rows=0)
            # fill pale
            for tc in tbl.iter(W + "tc"):
                set_cell_shading(tc, SIC_PALE)
                set_tc_borders(tc, SIC_BLUE, "6")
            nodes.append(tbl)
            nodes.append(paragraph(run(""), after=40, line=120))
            tex = tex[m.end():]
            continue

        m = re.match(r"\\begin\{figure\}(.*?)\\end\{figure\}", tex, re.S)
        if m:
            block = m.group(1)
            caption = ""
            cm = re.search(r"\\caption\s*\{", block)
            if cm:
                caption, _ = grab_braced(block, cm.end() - 1)
            idx = fig_idx[0]
            fig_idx[0] += 1
            name = fig_files[idx] if idx < len(fig_files) else fig_files[-1]
            path = FIGS / f"{name}.png"
            global FIG_SEQ
            FIG_SEQ += 1
            nodes.append(("IMAGE", path, f"Figure {FIG_SEQ}. {caption}"))
            tex = tex[m.end():]
            continue

        m = re.match(r"\\begin\{table\}(.*?)\\end\{table\}", tex, re.S)
        if m:
            block = m.group(1)
            caption = None
            cm = re.search(r"\\caption\s*\{", block)
            if cm:
                caption, _ = grab_braced(block, cm.end() - 1)
            # find tabular inside block (may have nested-brace column specs)
            tm = re.search(r"\\begin\{tabularx?\}", block)
            if tm:
                tab = match_tabular_env(block[tm.start():])
                if tab:
                    spec, inner, _ = tab
                    nodes.extend(emit_table("{" + spec + "}" + inner, caption))
                else:
                    # fallback: raw block as one table attempt
                    nodes.extend(emit_table(block, caption))
            else:
                nodes.extend(emit_table(block, caption))
            tex = tex[m.end():]
            continue

        # drop leftover {\small wrappers before blocks
        tex = re.sub(r"^\{\s*\\(small|footnotesize|scriptsize|noindent)+\s*", "", tex.lstrip())
        tex = re.sub(r"^\{\s*", "", tex.lstrip())

        tab = match_tabular_env(tex)
        if tab:
            spec, inner, end_i = tab
            nodes.extend(emit_table("{" + spec + "}" + inner, None))
            tex = tex[end_i:]
            continue

        m = re.match(
            r"\\begin\{(itemize|enumerate)\}(\s*\[[^\]]*\])?(.*?)\\end\{\1\}",
            tex, re.S,
        )
        if m:
            kind, opts, body = m.group(1), m.group(2) or "", m.group(3)
            label_m = re.search(r"label=\\textbf\{([^{}]*)\}", opts)
            label_fmt = label_m.group(1) if label_m else opts
            items = re.split(r"\\item\b", body)
            n = 0
            for it in items[1:]:
                n += 1
                it = re.sub(r"\\label\{[^}]*\}", "", it).strip()
                if kind == "enumerate":
                    if "RQ" in label_fmt:
                        prefix = f"RQ{n} "
                    elif re.search(r"\bO", label_fmt) or "O\\arabic" in label_fmt:
                        prefix = f"O{n} "
                    elif "F" in label_fmt:
                        prefix = f"F{n} "
                    elif "alph" in opts or "alph" in label_fmt:
                        prefix = f"({chr(96 + n)}) "
                    else:
                        prefix = f"{n}. "
                    nodes.append(paragraph(
                        run(prefix, size=21, bold=True),
                        *rich_runs(it, size=21),
                        left=284, hanging=284, after=40, line=284,
                    ))
                else:
                    nodes.append(paragraph(
                        run("• ", size=21, bold=True),
                        *rich_runs(it, size=21),
                        left=284, hanging=284, after=40, line=284,
                    ))
            tex = tex[m.end():]
            continue

        m = re.match(
            r"\\begin\{thebibliography\}\{[^}]*\}(.*?)\\end\{thebibliography\}",
            tex, re.S,
        )
        if m:
            add_banner("References", None)
            body = m.group(1)
            bibn = 0
            for bm in re.finditer(r"\\bibitem\{([^}]*)\}(.*?)(?=\\bibitem|\Z)", body, re.S):
                bibn += 1
                entry = bm.group(2).strip()
                entry = re.sub(r"\\newblock\s*", " ", entry)
                nodes.append(paragraph(
                    run(f"[{bibn}] ", size=19, bold=True),
                    *rich_runs(entry, size=19),
                    left=454, hanging=454, after=60, line=250,
                ))
            tex = tex[m.end():]
            continue

        # abstract fcolorbox — brace-aware
        if tex.startswith("\\fcolorbox"):
            i = 0
            # \fcolorbox{..}{..}{ content }
            m2 = re.match(r"\\fcolorbox", tex)
            i = m2.end()
            for _ in range(2):
                while i < len(tex) and tex[i] in " \n\t":
                    i += 1
                if i < len(tex) and tex[i] == "{":
                    i = match_braced(tex, i)
            while i < len(tex) and tex[i] in " \n\t":
                i += 1
            if i < len(tex) and tex[i] == "{":
                inner, end = grab_braced(tex, i)
            else:
                inner, end = "", i
            if "Abstract" in inner[:120]:
                # unwrap \parbox{...}{ body } if present
                body = inner
                pm = re.search(r"\\parbox", inner)
                if pm:
                    j = pm.end()
                    while j < len(inner) and inner[j] in " \n\t":
                        j += 1
                    if j < len(inner) and inner[j] == "{":
                        j = match_braced(inner, j)  # width
                    while j < len(inner) and inner[j] in " \n\t":
                        j += 1
                    if j < len(inner) and inner[j] == "{":
                        body, _ = grab_braced(inner, j)
                body = body.replace("\\vspace{2pt}", "")
                runs_ = rich_runs(body, size=21)
                tbl = make_table([[runs_]], [9010], header_rows=0)
                for tc in tbl.iter(W + "tc"):
                    set_cell_shading(tc, "FFFFFF")
                    set_tc_borders(tc, SIC_RULE, "6")
                nodes.append(tbl)
                nodes.append(paragraph(run(""), after=40, line=120))
                tex = tex[end:]
                continue

        # paragraph: stop at next block command
        stop = re.search(
            r"\n\s*(\\section|\\subsection|\\begin\{|\\finding\{|\\bibitem|\\PAGEBREAK)",
            tex,
        )
        if stop:
            para = tex[:stop.start()]
            tex = tex[stop.start():]
        else:
            para = tex
            tex = ""
        para = re.sub(r"\s+", " ", para).strip()
        para = re.sub(r"^\{\s*\\(small|footnotesize|normalsize)\s*", "", para)
        para = re.sub(r"^\{\s*", "", para)
        para = re.sub(r"\\par\s*\}?\s*$", "", para)
        para = para.strip().strip("{}").strip()
        if para:
            nodes.append(paragraph(*rich_runs(para, size=21), after=100, line=284))
    return nodes


def fill_cover_sdt(sdt, text: str, *, font=FONT_B, size=24, color=BODY_COLOR, bold=True):
    content = sdt.find(W + "sdtContent")
    if content is None:
        return
    paras = content.findall(W + "p")
    if not paras:
        return
    # keep first paragraph as template for formatting
    p0 = paras[0]
    pPr = p0.find(W + "pPr")
    for extra in paras[1:]:
        content.remove(extra)
    for r in p0.findall(W + "r"):
        p0.remove(r)
    lines = text.split("||")
    for i, line in enumerate(lines):
        if i:
            # soft line break
            r = el("r")
            br = el("br")
            r.append(br)
            p0.append(r)
        p0.append(run(line, font=font, size=size, bold=bold, color=color))


def main():
    global SEC_NO, SUB_NO, FIG_SEQ, TAB_SEQ
    SEC_NO = SUB_NO = FIG_SEQ = TAB_SEQ = 0
    load_macros()
    print("macros", len(MACROS))

    # parse body from main.tex
    main_tex = (LATEX / "main.tex").read_text(encoding="utf-8")
    main_tex = strip_comments(main_tex)
    if "\\begin{document}" in main_tex:
        main_tex = main_tex.split("\\begin{document}", 1)[1]
    build_cite_order(main_tex)
    build_autoref_map(main_tex)
    print("cites", len(CITE_ORDER), "autorefs", len(AUTOREF))
    # drop cover: \siccover{a}{b}{c}{d} — brace-aware, 4 groups
    if "\\siccover" in main_tex:
        i = main_tex.find("\\siccover")
        j = i + len("\\siccover")
        for _ in range(4):
            while j < len(main_tex) and main_tex[j] in " \n\t":
                j += 1
            if j < len(main_tex) and main_tex[j] == "{":
                j = match_braced(main_tex, j)
            else:
                break
        main_tex = main_tex[:i] + main_tex[j:]
    main_tex = main_tex.replace("\\siccontents", "")
    # keep team/instructor sections out of generic parse — handled at end
    team_split = re.split(r"\\section\{Team Member Review", main_tex)
    body_tex = team_split[0]
    team_tex = ("\\section{Team Member Review" + team_split[1]) if len(team_split) > 1 else ""

    nodes = collect_body_nodes(body_tex)
    print("body nodes", len(nodes),
          "figures", FIG_SEQ, "tables", TAB_SEQ)

    # load template
    zin, doc_xml = load_template_parts()
    root = etree.fromstring(doc_xml)
    body = root.find(W + "body")
    kids = list(body)

    # identify regions
    # cover: kids 0-18 (p), cover SDTs 20-42, TOC 53-77, body SDTs 83-117,
    # team/instructor 118-125, then sectPr
    sectPr = kids[-1]

    # fill cover SDTs by tag
    tag_map = {
        # Sharp Sans embed is a subset — use SamsungOne-700 for filled cover text
        "goog_rdk_7": (
            "Bayan: On-Device Arabic Text Simplification||for Readers with Dyslexia",
            FONT_B, 40, "000000",
        ),
        "goog_rdk_18": ("05/10/26", FONT_B, 36, "000000"),
        "goog_rdk_32": ("Cogni", FONT_B, 48, "000000"),
        "goog_rdk_34": ("Marwan Elamami", FONT_B, 24, "000000"),
        "goog_rdk_35": ("Abdulrahman Khengari", FONT_B, 24, "000000"),
        "goog_rdk_36": ("Ahmed Alaeb", FONT_B, 24, "000000"),
        "goog_rdk_37": ("Sanad Ali", FONT_B, 24, "000000"),
        "goog_rdk_38": ("Mohammed Thabet", FONT_B, 24, "000000"),
        "goog_rdk_39": ("Abdul Majid Mraied", FONT_B, 24, "000000"),
    }
    # 6th member may share tag
    for sdt in root.findall(".//" + W + "sdt"):
        pr = sdt.find(W + "sdtPr")
        if pr is None:
            continue
        tag = pr.find(W + "tag")
        val = tag.get(W + "val") if tag is not None else ""
        if val in tag_map:
            text, font, size, color = tag_map[val]
            fill_cover_sdt(sdt, text, font=font, size=size, color=color, bold=True)
        elif val == "goog_rdk_1":
            # duplicate title placeholder in the template — clear it
            fill_cover_sdt(sdt, "", font=FONT_B, size=40, bold=True)

    # rebuild TOC region: kids 53-77 → replace with our TOC
    # find index of Content SDT and first body SDT
    kids_now = list(body)
    content_idx = None
    body_start_idx = None
    team_idx = None
    for i, el_ in enumerate(kids_now):
        tag = el_.find(W + "sdtPr/" + W + "tag")
        t = tag.get(W + "val") if tag is not None else ""
        text = "".join(x.text or "" for x in el_.iter(W + "t"))
        if content_idx is None and t == "goog_rdk_40":
            content_idx = i
        if body_start_idx is None and t == "goog_rdk_79":
            body_start_idx = i
        if team_idx is None and "Team Member Review" in text and i > 80:
            team_idx = i

    print("indices", content_idx, body_start_idx, team_idx)
    assert content_idx is not None and body_start_idx is not None

    # Build TOC nodes
    toc_nodes = []
    toc_nodes.append(paragraph(
        run("Content", font=SHARP, size=48, bold=True, color=SIC_BLUE),
        align="center", after=200, line=560,
    ))
    toc_entries = [
        (1, "1. Introduction"),
        (2, "1.1. Background Information"),
        (2, "1.2. Motivation and Objective"),
        (2, "1.3. Members and Role Assignments"),
        (2, "1.4. Schedule and Milestones"),
        (1, "2. Project Execution"),
        (2, "2.1. Data Acquisition"),
        (2, "2.2. Training Methodology"),
        (2, "2.3. Workflow"),
        (2, "2.4. System Design"),
        (1, "3. Results"),
        (2, "3.1. Data Preprocessing"),
        (2, "3.2. Exploratory Data Analysis (EDA)"),
        (2, "3.3. Modeling"),
        (2, "3.4. User Interface"),
        (2, "3.5. Testing and Improvements"),
        (1, "4. Projected Impact"),
        (2, "4.1. Accomplishments and Benefits"),
        (2, "4.2. Future Improvements"),
        (2, "References"),
        (1, "5. Team Member Review and Comment"),
        (1, "6. Instructor Review and Comment"),
    ]
    for lvl, title in toc_entries:
        if lvl == 1:
            toc_nodes.append(paragraph(
                run(title, font=FONT_B, size=24, bold=True),
                after=100, line=276,
            ))
        else:
            toc_nodes.append(paragraph(
                run(title, font=FONT, size=22),
                left=284, after=60, line=260,
            ))
    toc_nodes.append(page_break())

    # Assemble new body children
    # keep 0 .. content_idx-1 (cover + spacers)
    # insert toc_nodes
    # insert page break + body nodes
    # keep team_idx .. sectPr (team review tables etc)
    # But body_start_idx .. team_idx-1 are template placeholders — drop them

    new_kids = list(kids_now[:content_idx])
    for n in toc_nodes:
        new_kids.append(n)
    def drop_empty_paras(kids, keep_before=50):
        out = []
        for i, n in enumerate(kids):
            if i >= keep_before and n.tag == W + "p":
                txt = "".join(t.text or "" for t in n.iter(W + "t")).strip()
                has_draw = n.find(".//" + W + "drawing") is not None
                if not txt and not has_draw:
                    continue
            out.append(n)
        return out

    # body content (toc_nodes already ends with a page break)
    for n in nodes:
        if isinstance(n, tuple) and n[0] == "IMAGE":
            _, path, caption = n
            p = paragraph(align="center", after=80, line=0, line_rule="auto")
            width_emu = 5735955
            try:
                from PIL import Image
                with Image.open(path) as im:
                    w, h = im.size
                height_emu = int(width_emu * h / w)
            except Exception:
                height_emu = int(width_emu * 0.55)
            rid = f"rIdImg{FIG_SEQ}"
            p.set("img-rid", rid)
            add_image_para(p, path, width_emu, height_emu)
            del p.attrib["img-rid"]
            new_kids.append(p)
            new_kids.append(paragraph(
                run(caption.split(". ", 1)[0] + ". ", size=19, bold=True, color=SIC_BLUE),
                *rich_runs(caption.split(". ", 1)[1] if ". " in caption else caption, size=19),
                after=160, line=250,
            ))
        else:
            new_kids.append(n)

    # team review banner + real template tables
    if team_idx is not None:
        for n in kids_now[team_idx:]:
            text = "".join(x.text or "" for x in n.iter(W + "t"))
            if "Instructor Review" in text:
                new_kids.append(page_break())
            new_kids.append(n)
    else:
        new_kids.append(sectPr)

    # drop leftover template spacer paragraphs after the cover
    new_kids = drop_empty_paras(new_kids, keep_before=50)

    def compact_tables(kids):
        for n in kids:
            if n.tag != W + "tbl":
                continue
            for tr in n.findall(W + "tr"):
                trPr = tr.find(W + "trPr")
                if trPr is None:
                    trPr = el("trPr")
                    tr.insert(0, trPr)
                if trPr.find(W + "cantSplit") is None:
                    trPr.append(el("cantSplit"))
                if trPr.find(W + "tblHeader") is None and tr is n.find(W + "tr"):
                    trPr.append(el("tblHeader"))
        return kids

    new_kids = compact_tables(new_kids)

    # rebuild body
    for child in list(body):
        body.remove(child)
    for n in new_kids:
        if n is sectPr:
            continue
        body.append(n)
    body.append(sectPr)

    # footer: rewrite footer1.xml fields
    footer_xml = zin.read("word/footer1.xml").decode("utf-8")
    # replace static Page 2 / 7 with fields
    # simpler: put PAGE and NUMPAGES fldSimple
    new_footer = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:p>
    <w:pPr>
      <w:spacing w:before="0" w:after="0" w:line="240" w:lineRule="auto"/>
      <w:jc w:val="right"/>
      <w:ind w:right="400"/>
    </w:pPr>
    <w:r>
      <w:rPr>
        <w:rFonts w:ascii="SamsungOne-400" w:hAnsi="SamsungOne-400"/>
        <w:sz w:val="20"/><w:szCs w:val="20"/>
      </w:rPr>
      <w:t xml:space="preserve">Page </w:t>
    </w:r>
    <w:fldSimple w:instr=" PAGE ">
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="SamsungOne-400" w:hAnsi="SamsungOne-400"/>
          <w:sz w:val="20"/><w:szCs w:val="20"/>
        </w:rPr>
        <w:t>1</w:t>
      </w:r>
    </w:fldSimple>
    <w:r>
      <w:rPr>
        <w:rFonts w:ascii="SamsungOne-400" w:hAnsi="SamsungOne-400"/>
        <w:sz w:val="20"/><w:szCs w:val="20"/>
      </w:rPr>
      <w:t xml:space="preserve"> / </w:t>
    </w:r>
    <w:fldSimple w:instr=" NUMPAGES ">
      <w:r>
        <w:rPr>
          <w:rFonts w:ascii="SamsungOne-400" w:hAnsi="SamsungOne-400"/>
          <w:sz w:val="20"/><w:szCs w:val="20"/>
        </w:rPr>
        <w:t>1</w:t>
      </w:r>
    </w:fldSimple>
  </w:p>
</w:ftr>'''

    # collect IMAGE nodes paths
    img_paths = []
    for n in nodes:
        if isinstance(n, tuple) and n[0] == "IMAGE":
            img_paths.append(n[1])

    zin.close()
    _write_with_images(OUT, TEMPLATE, root, img_paths, new_footer)
    print("wrote", OUT, "size", OUT.stat().st_size)


def _write_with_images(out_path, template_path, doc_root, img_paths, footer_xml):
    """Write final docx with image relationships."""
    # find rIds referenced in document
    embeds = []
    for blip in doc_root.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
        embeds.append(blip)

    zin = zipfile.ZipFile(template_path)
    rels_name = "word/_rels/document.xml.rels"
    rels_xml = zin.read(rels_name)
    rels_root = etree.fromstring(rels_xml)

    REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
    # remove old image rels if any; add new
    used = set()
    for r in rels_root:
        used.add(r.get("Id"))

    # assign rIds in order of blip references
    n = 200
    for blip, path in zip(embeds, img_paths):
        rid = f"rId{n}"
        n += 1
        blip.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed", rid)
        rel = etree.SubElement(rels_root, "{%s}Relationship" % REL_NS)
        rel.set("Id", rid)
        rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
        ext = path.suffix.lower().replace(".", "")
        rel.set("Target", f"media/fig{n}.{ext}")

    # content types
    ct_xml = zin.read("[Content_Types].xml").decode("utf-8")

    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zout:
        media = {}
        n = 200
        for blip, path in zip(embeds, img_paths):
            n += 1
            ext = path.suffix.lower().replace(".", "")
            media[f"word/media/fig{n}.{ext}"] = path.read_bytes()

        for item in zin.infolist():
            name = item.filename
            if name == "word/document.xml":
                zout.writestr(name, etree.tostring(
                    doc_root, xml_declaration=True, encoding="UTF-8", standalone=True))
            elif name == "word/footer1.xml":
                zout.writestr(name, footer_xml.encode("utf-8"))
            elif name == rels_name:
                zout.writestr(name, etree.tostring(
                    rels_root, xml_declaration=True, encoding="UTF-8", standalone=True))
            elif name == "[Content_Types].xml":
                # ensure png/jpeg defaults
                extra = ""
                if 'Extension="png"' not in ct_xml:
                    extra += '<Default Extension="png" ContentType="image/png"/>'
                if 'Extension="jpeg"' not in ct_xml and 'Extension="jpg"' not in ct_xml:
                    extra += '<Default Extension="jpeg" ContentType="image/jpeg"/>'
                if extra:
                    ct_xml = ct_xml.replace("</Types>", extra + "</Types>")
                zout.writestr(name, ct_xml.encode("utf-8"))
            else:
                zout.writestr(item, zin.read(name))
        for name, data in media.items():
            zout.writestr(name, data)
    zin.close()


if __name__ == "__main__":
    main()
