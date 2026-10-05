"""Small toolkit for the PowerPoint-native (submission) deck: shapes in inches, plus click-by-click entrance/exit
animations written as raw PresentationML (python-pptx has no animation API).

Coordinates are inches from the slide's top-left. One "step" = one click; every effect in a step starts together,
offset by its own delay (ms). A step can be `auto` (plays when the slide appears, no click needed).
"""
from lxml import etree
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.oxml.ns import qn
from pptx.util import Emu, Inches, Pt

PAPER, PAPER2, PAPER3 = "F6F2E6", "EFE9D9", "E6DFCC"
INK, INK2, INK3, INK4 = "282824", "4A4842", "6F6B5E", "A29D8C"
NIGHT, NIGHT2, CREAM = "1A1A14", "26261E", "F2EFE2"
SUN, SUN_DK, SUN_LT = "C6986B", "8A5E35", "EEDDC7"
WARN, WARN_LT = "B5533C", "F3E2DA"

LATIN, ARABIC, ARABIC_DISPLAY = "Readex Pro", "Noto Naskh Arabic", "Amiri"
SW, SH = 10.83, 7.5  # slide size in inches (template: 9902825 x 6858000 EMU)

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def rgb(h):
    return RGBColor.from_string(h)


def _alpha(fill_parent, alpha):
    """alpha in 0..1 on the solidFill inside fill_parent (an element holding a:solidFill)."""
    clr = fill_parent.find(".//" + qn("a:srgbClr"))
    a = etree.SubElement(clr, qn("a:alpha"))
    a.set("val", str(int(alpha * 100000)))


class Canvas:
    """One slide + its animation steps."""

    def __init__(self, prs, layout, bg):
        self.slide = prs.slides.add_slide(layout)
        for ph in list(self.slide.placeholders):
            ph._element.getparent().remove(ph._element)
        self.sh = self.slide.shapes
        self.steps = []  # list of dict(auto, effects=[(shape, kind, delay, dur, opts)])
        self.rect(0, 0, SW, SH, bg, name="Background")

    # ---- shapes
    def _style(self, s, fill, line=None, line_w=1.0, alpha=None):
        if fill is None:
            s.fill.background()
        else:
            s.fill.solid()
            s.fill.fore_color.rgb = rgb(fill)
            if alpha is not None:
                _alpha(s._element.spPr.find(qn("a:solidFill")), alpha)
        if line is None:
            s.line.fill.background()
        else:
            s.line.color.rgb = rgb(line)
            s.line.width = Pt(line_w)
        s.shadow.inherit = False

    def rect(self, x, y, w, h, fill, line=None, line_w=1.0, radius=None, alpha=None, name=None, oval=False):
        kind = MSO_SHAPE.OVAL if oval else (MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE)
        s = self.sh.add_shape(kind, Inches(x), Inches(y), Inches(w), Inches(h))
        if radius and not oval:
            s.adjustments[0] = min(0.5, radius / min(w, h))
        self._style(s, fill, line, line_w, alpha)
        if name:
            s.name = name
        return s

    def circle(self, cx, cy, r, fill, **kw):
        return self.rect(cx - r, cy - r, 2 * r, 2 * r, fill, oval=True, **kw)

    def text(self, x, y, w, h, s, size, color=INK, bold=False, align="l", font=LATIN, rtl=False, shape=None,
             line_spacing=None, anchor="m", name=None):
        """Text in a new textbox (or inside `shape`). `s` may contain \\n for separate paragraphs; `s` may also be a list
        of (text, size, color, bold, font) tuples, one per paragraph."""
        tb = shape or self.sh.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
        tf.vertical_anchor = {"m": MSO_ANCHOR.MIDDLE, "t": MSO_ANCHOR.TOP, "b": MSO_ANCHOR.BOTTOM}[anchor]
        paras = s if isinstance(s, list) else [(t, size, color, bold, font) for t in s.split("\n")]
        for i, (t, sz, col, b, fnt) in enumerate(paras):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"l": PP_ALIGN.LEFT, "c": PP_ALIGN.CENTER, "r": PP_ALIGN.RIGHT}[align]
            if line_spacing:
                p.line_spacing = line_spacing
            r = p.add_run()
            r.text = t
            f = r.font
            f.size, f.bold, f.name = Pt(sz), b, fnt
            f.color.rgb = rgb(col)
            rpr = r._r.get_or_add_rPr()
            for tag in ("a:cs", "a:ea"):
                el = etree.SubElement(rpr, qn(tag))
                el.set("typeface", fnt)
            if fnt in (ARABIC, ARABIC_DISPLAY) or rtl:
                rpr.set("lang", "ar-SA")
                p._p.get_or_add_pPr().set("rtl", "1")
        if name:
            tb.name = name
        return tb

    def card(self, x, y, w, h, fill=PAPER2, line=PAPER3, radius=0.16, text=None, size=14, color=INK, bold=False,
             align="c", name=None, alpha=None):
        s = self.rect(x, y, w, h, fill, line=line, line_w=1.25, radius=radius, name=name, alpha=alpha)
        if text is not None:
            self.text(0, 0, 0, 0, text, size, color, bold, align, shape=s)
            s.text_frame.margin_left = s.text_frame.margin_right = Inches(0.12)
        return s

    def line(self, x1, y1, x2, y2, color, w=1.5, arrow=False):
        c = self.sh.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(x1), Inches(y1), Inches(x2), Inches(y2))
        c.line.color.rgb = rgb(color)
        c.line.width = Pt(w)
        if arrow:
            ln = c.line._get_or_add_ln()
            te = etree.SubElement(ln, qn("a:tailEnd"))
            te.set("type", "triangle")
        return c

    def pic(self, path, x, y, w, alt="", name=None):
        p = self.sh.add_picture(str(path), Inches(x), Inches(y), width=Inches(w))
        p._element.nvPicPr.cNvPr.set("descr", alt)
        if name:
            p.name = name
        return p

    def add_movie(self, path, x, y, w, h, poster=None, alt="", name=None):
        """Embed a video that autoplays when the slide appears. `poster` is a PNG path for the
        first frame; if omitted the first frame of the video is used."""
        mv = self.sh.add_movie(str(path), Inches(x), Inches(y), Inches(w), Inches(h),
                               poster_frame_image=str(poster) if poster else None,
                               mime_type="video/mp4")
        mv._element.nvPicPr.cNvPr.set("descr", alt)
        if name:
            mv.name = name
        # autoplay timing: same mechanism as assemble_presenting.py
        from lxml import etree as _et
        timing_xml = (
            '<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
            '<p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot">'
            '<p:childTnLst><p:video><p:cMediaNode vol="80000">'
            f'<p:cTn id="2" fill="hold" display="0"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
            f'<p:tgtEl><p:spTgt spid="{mv.shape_id}"/></p:tgtEl>'
            '</p:cMediaNode></p:video></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
        )
        self.slide._element.append(_et.fromstring(timing_xml))
        return mv

    def group(self, shapes, name=None):
        g = self.sh.add_group_shape(shapes)
        if name:
            g.name = name
        return g

    # ---- animation
    def step(self, *effects, auto=False):
        """effects: (shape, kind[, delay_ms[, dur_ms]]) with kind in fade | wipe_left | wipe_up | wipe_right | fade_out."""
        norm = []
        for e in effects:
            shape, kind = e[0], e[1]
            delay = e[2] if len(e) > 2 else 0
            dur = e[3] if len(e) > 3 else (900 if kind.startswith("wipe") else 500)
            norm.append((shape, kind, delay, dur))
        self.steps.append({"auto": auto, "effects": norm})

    def finish(self, notes):
        self.slide.notes_slide.notes_text_frame.text = notes
        if self.steps:
            self.slide._element.append(build_timing(self.steps))


# ---- timing XML ---------------------------------------------------------------------------------
_PRESETS = {  # kind -> (presetID, class, subtype, filter, transition)
    "fade": (10, "entr", 0, "fade", "in"),
    "wipe_left": (22, "entr", 8, "wipe(left)", "in"),
    "wipe_right": (22, "entr", 2, "wipe(right)", "in"),
    "wipe_up": (22, "entr", 4, "wipe(down)", "in"),  # "from bottom"
    "fade_out": (10, "exit", 0, "fade", "out"),
}


def build_timing(steps):
    ids = iter(range(3, 10000))
    parts = []
    bld = {}
    for si, st in enumerate(steps):
        outer, inner = next(ids), next(ids)
        conds = '<p:cond delay="indefinite"/>'
        if st["auto"] and si == 0:
            conds += '<p:cond evt="onBegin" delay="0"><p:tn val="2"/></p:cond>'
        effs = []
        for ei, (shape, kind, delay, dur) in enumerate(st["effects"]):
            pid, cls, sub, filt, trans = _PRESETS[kind]
            node = ("afterEffect" if st["auto"] else "clickEffect") if ei == 0 else "withEffect"
            spid = shape.shape_id
            tgt = f'<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl>'
            vis_delay = 0 if trans == "in" else dur
            vis_val = "visible" if trans == "in" else "hidden"
            beh = (
                f'<p:set><p:cBhvr><p:cTn id="{next(ids)}" dur="1" fill="hold"><p:stCondLst><p:cond delay="{vis_delay}"/></p:stCondLst></p:cTn>'
                f'{tgt}<p:attrNameLst><p:attrName>style.visibility</p:attrName></p:attrNameLst></p:cBhvr>'
                f'<p:to><p:strVal val="{vis_val}"/></p:to></p:set>'
                f'<p:animEffect transition="{trans}" filter="{filt}"><p:cBhvr><p:cTn id="{next(ids)}" dur="{dur}"/>{tgt}</p:cBhvr></p:animEffect>'
            )
            effs.append(
                f'<p:par><p:cTn id="{next(ids)}" presetID="{pid}" presetClass="{cls}" presetSubtype="{sub}" fill="hold" grpId="0" '
                f'nodeType="{node}"><p:stCondLst><p:cond delay="{delay}"/></p:stCondLst><p:childTnLst>{beh}</p:childTnLst></p:cTn></p:par>'
            )
            if shape._element.tag == qn("p:sp"):
                bld[spid] = True
        parts.append(
            f'<p:par><p:cTn id="{outer}" fill="hold"><p:stCondLst>{conds}</p:stCondLst><p:childTnLst>'
            f'<p:par><p:cTn id="{inner}" fill="hold"><p:stCondLst><p:cond delay="0"/></p:stCondLst><p:childTnLst>'
            + "".join(effs) + "</p:childTnLst></p:cTn></p:par></p:childTnLst></p:cTn></p:par>"
        )
    bld_xml = "".join(f'<p:bldP spid="{spid}" grpId="0" animBg="1"/>' for spid in bld)
    xml = (
        f'<p:timing xmlns:p="{P}"><p:tnLst><p:par><p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst>'
        '<p:seq concurrent="1" nextAc="seek"><p:cTn id="2" dur="indefinite" nodeType="mainSeq"><p:childTnLst>'
        + "".join(parts)
        + '</p:childTnLst></p:cTn><p:prevCondLst><p:cond evt="onPrev" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:prevCondLst>'
        '<p:nextCondLst><p:cond evt="onNext" delay="0"><p:tgtEl><p:sldTgt/></p:tgtEl></p:cond></p:nextCondLst></p:seq>'
        f"</p:childTnLst></p:cTn></p:par></p:tnLst><p:bldLst>{bld_xml}</p:bldLst></p:timing>"
    )
    return etree.fromstring(xml)
