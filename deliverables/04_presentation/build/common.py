"""Shared look for the Bayan pitch deck: Bayan design-system palette on the SIC template's aspect ratio."""
from pathlib import Path

from manim import *
from manim_slides import Slide  # noqa: F401  (kept so scenes can be turned into live slides)
from manim_slides.config import BaseSlideConfig

HERE = Path(__file__).parent
ASSETS = HERE / "assets"

# Frame matches the SIC template (9902825 x 6858000 EMU = 1.444:1)
config.frame_height = 8
config.frame_width = 8 * 9902825 / 6858000

PAPER, PAPER2, PAPER3 = "#F6F2E6", "#EFE9D9", "#E6DFCC"
INK, INK2, INK3, INK4 = "#282824", "#4A4842", "#6F6B5E", "#A29D8C"
NIGHT, NIGHT2, CREAM = "#1A1A14", "#26261E", "#F2EFE2"
SUN, SUN_DK, SUN_LT = "#C6986B", "#8A5E35", "#EEDDC7"
WARN, WARN_LT = "#B5533C", "#F3E2DA"

W, H = config.frame_width, config.frame_height
LEFT_X, RIGHT_X = -W / 2 + 0.7, W / 2 - 0.7

LATIN = "Readex Pro"
ARABIC = "Noto Naskh Arabic"
ARABIC_DISPLAY = "Amiri"


TEXT_SCALE = 0.8   # deck sizes are written in "slide points"; Manim's own font_size runs ~1.4x larger
SUPER = 4           # render glyphs at 4x and scale down: avoids uneven letter spacing at small sizes
MIN_SIZE = 11       # nothing on a slide may be smaller than this at slide size (the 29 Sep deck had ~8)


def T(s, size=28, color=INK, weight=NORMAL, **kw):
    size = max(size, MIN_SIZE)
    t = Text(s, font=LATIN, font_size=size * TEXT_SCALE * SUPER, color=color, weight=weight, **kw)
    return t.scale(1 / SUPER)


def A(s, size=40, color=INK, font=ARABIC):
    # MarkupText, not Text: Text silently drops single Arabic words (see SPIKE_NOTES.md)
    size = max(size, MIN_SIZE)
    return MarkupText(s, font=font, font_size=size * TEXT_SCALE * SUPER, color=color).scale(1 / SUPER)


def fit(m, w=None, h=None):
    """Shrink m to fit inside w x h (never enlarges)."""
    if w and m.width > w:
        m.scale_to_fit_width(w)
    if h and m.height > h:
        m.scale_to_fit_height(h)
    return m


def at_left(m, x=LEFT_X):
    m.shift(RIGHT * (x - m.get_left()[0]))
    return m


def svg(name, width=None, height=None):
    m = SVGMobject(str(ASSETS / name))
    if width:
        m.scale_to_fit_width(width)
    if height:
        m.scale_to_fit_height(height)
    return m


def sun(r=0.12, color=SUN):
    return Circle(radius=r, color=color, fill_opacity=1, stroke_width=0)


def card(w, h, fill=PAPER2, stroke=PAPER3, r=0.18):
    return RoundedRectangle(width=w, height=h, corner_radius=r, fill_color=fill, fill_opacity=1,
                            stroke_color=stroke, stroke_width=2)


def chip(text, fill=SUN_LT, color=SUN_DK, size=20, padx=0.35, pady=0.16, weight=MEDIUM):
    t = T(text, size, color, weight)
    box = RoundedRectangle(width=t.width + 2 * padx, height=t.height + 2 * pady, corner_radius=0.2,
                           fill_color=fill, fill_opacity=1, stroke_width=0)
    t.move_to(box)
    return VGroup(box, t)


def source_badge(text, size=11):
    """Small provenance label for the corner of a chart. This is what stops claims going unsourced."""
    bar = Rectangle(width=0.06, height=size * 0.028, fill_color=SUN, fill_opacity=1, stroke_width=0)
    t = T(text, size, INK3)
    bar.next_to(t, LEFT, buff=0.14, aligned_edge=DOWN)
    return VGroup(bar, t)  # caller positions the group


def _dot(pos, r, color):
    c = Circle(radius=r, fill_color=color, fill_opacity=1, stroke_width=0)
    c.move_to([pos[0], pos[1], 0])
    return c


def scatter(points, width=6.2, height=3.7, x_lab="meaning kept (%)", y_lab="longest clause: words shorter",
            x_range=(35, 105), y_range=(-0.5, 7.0), badge=None):
    """points: [(label, x, y, mark)] where mark is 'copy' | 'app' | 'model2' | 'ship'.

    Returns a VGroup of the whole plot: axes, points, axis labels, and the badge. Caller positions it.
    """
    style = {
        "copy":    (INK4,  0.11, "copy: 100% meaning, 0 simplification"),
        "app":     (SUN_DK, 0.13, "today's app"),
        "model2":  (INK3,  0.11, "model 2"),
        "ship":    (WARN,  0.17, "model 3 + safety net"),
    }
    x0, x1 = x_range
    y0, y1 = y_range
    ax = VGroup()
    ax.add(Line([-width / 2, -height / 2, 0], [width / 2, -height / 2, 0], stroke_color=INK4, stroke_width=2))
    ax.add(Line([-width / 2, -height / 2, 0], [-width / 2, height / 2, 0], stroke_color=INK4, stroke_width=2))

    def xy(x, y):
        px = -width / 2 + (x - x0) / (x1 - x0) * width
        py = -height / 2 + (y - y0) / (y1 - y0) * height
        return px, py

    pts = VGroup()
    for lab, x, y, mark in points:
        col, r, _ = style.get(mark, (INK3, 0.11, lab))
        px, py = xy(x, y)
        if mark == "ship":
            halo = Circle(radius=r * 2.1, stroke_color=col, stroke_width=1.5, fill_opacity=0)
            halo.move_to([px, py, 0])
            pts.add(halo)
        pts.add(_dot((px, py), r, col))
        if mark in ("copy", "ship", "app"):
            tag = T(lab, 12, INK2, MEDIUM) if mark != "ship" else T(lab, 12, WARN, SEMIBOLD)
            if mark == "ship":      # clear of the halo, towards the empty right side
                tag.next_to([px, py, 0], RIGHT, buff=r * 2.1 + 0.08)
            elif mark == "app" and x < 60:   # another point sits just below this one
                tag.next_to([px, py, 0], LEFT, buff=0.2)
            else:
                tag.next_to([px, py, 0], UP if y < (y0 + y1) / 2 else DOWN, buff=0.16)
            pts.add(tag)

    labs = VGroup()
    xl = T(x_lab, 11, INK3)
    xl.next_to(ax[0], DOWN, buff=0.18)
    labs.add(xl)
    yl = T(y_lab, 11, INK3)
    yl.rotate(PI / 2)
    yl.next_to(ax[1], LEFT, buff=0.18)
    labs.add(yl)

    out = VGroup(ax, pts, labs)
    if badge:
        b = source_badge(badge)
        b.move_to([width / 2, -height / 2 - 0.62, 0], aligned_edge=RIGHT)
        out.add(b)
    return out


class Deck(Slide):
    """One scene = one beat. `begin_beat()` + `step()` cut it into steps.

    Within a beat the steps advance on their own and the beat stops at its end: that is
    "stop at certain points automatically". manim-slides applies `auto_next` to the slide
    *after* a `next_slide()` call, and gives the first slide a default config, hence the two
    helpers rather than raw `next_slide()` calls.
    """
    NUM, KICKER, TITLE = 0, "", ""
    DARK = False
    TOTAL = 10

    def begin_beat(self):
        """Let the first step of this beat advance on its own once it has played."""
        self._base_slide_config = BaseSlideConfig(auto_next=True)

    def step(self, src=None, notes=None):
        """Close the current step. The next step plays on its own once this one ends."""
        self._cut(auto_next=True, src=src, notes=notes)

    def hold(self, src=None, notes=None):
        """Close the current step and make the next one stop here. Use on the beat's last
        boundary, so the beat plays through and then holds."""
        self._cut(auto_next=False, src=src, notes=notes)

    def audit(self, tag):
        """Warn when anything sits outside the safe area (side margins, or low enough to hit the footer)."""
        skip = {id(self._foot), id(self.header)}
        for m in self.mobjects:
            if id(m) in skip or not len(m.submobjects) and not m.has_points():
                continue
            l, r, t, b = m.get_left()[0], m.get_right()[0], m.get_top()[1], m.get_bottom()[1]
            if l < -W / 2 + 0.3 or r > W / 2 - 0.3 or b < -H / 2 + 1.0 or t > H / 2:
                print(f"AUDIT {type(self).__name__} {tag}: {type(m).__name__} x[{l:.2f},{r:.2f}] y[{b:.2f},{t:.2f}]", flush=True)

    def _cut(self, auto_next, src=None, notes=None):
        self.audit("step")
        kw = {"auto_next": auto_next}
        if src is not None:
            kw["src"] = src
        if notes is not None:
            kw["notes"] = notes
        self.next_slide(**kw)

    def chrome(self):
        fg = CREAM if self.DARK else INK
        self.camera.background_color = ManimColor(NIGHT if self.DARK else PAPER)
        items = []
        if self.KICKER:
            k = T(self.KICKER.upper(), 18, SUN, MEDIUM)
            k.move_to([LEFT_X, H / 2 - 0.75, 0], aligned_edge=LEFT)
            bar = Rectangle(width=0.08, height=k.height + 0.3, fill_color=SUN, fill_opacity=1, stroke_width=0)
            bar.next_to(k, LEFT, buff=0.2)
            items += [bar, k]
        if self.TITLE:
            t = T(self.TITLE, 40, fg, SEMIBOLD)
            t.next_to(items[-1], DOWN, buff=0.28, aligned_edge=LEFT)
            at_left(t)
            items.append(t)
        # footer: Samsung wordmark + programme name + slide number
        sam = svg("samsung-white.svg" if self.DARK else "samsung-blue.svg", width=1.25)
        sam.move_to([LEFT_X, -H / 2 + 0.5, 0], aligned_edge=LEFT)
        sic = T("Samsung Innovation Campus  ·  AI Course", 13, CREAM if self.DARK else INK3)
        sic.next_to(sam, RIGHT, buff=0.3)
        num = T(f"{self.NUM} / {self.TOTAL}", 13, CREAM if self.DARK else INK3)
        num.move_to([RIGHT_X, -H / 2 + 0.5, 0], aligned_edge=RIGHT)
        foot = VGroup(sam, sic, num)
        self._foot = foot
        self.add(foot)
        self.header = VGroup(*items)
        return self.header

    def construct(self):
        header = self.chrome()
        if len(header):
            self.play(FadeIn(header, shift=RIGHT * 0.3), run_time=0.7)
        self.build()
        self.audit("end")
        self.wait(1.5)

    def build(self):
        raise NotImplementedError
