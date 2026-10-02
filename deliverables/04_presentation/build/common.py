"""Shared look for the Bayan pitch deck: Bayan design-system palette on the SIC template's aspect ratio."""
from pathlib import Path

from manim import *
from manim_slides import Slide  # noqa: F401  (kept so scenes can be turned into live slides)

HERE = Path(__file__).parent
ASSETS = HERE / "assets"

# Frame matches the SIC template (9902825 x 6858000 EMU = 1.444:1)
config.frame_height = 8
config.frame_width = 8 * 9902825 / 6858000

PAPER, PAPER2, PAPER3 = "#F6F2E6", "#EFE9D9", "#E6DFCC"
INK, INK2, INK3, INK4 = "#282824", "#4A4842", "#6F6B5E", "#A29D8C"
NIGHT, NIGHT2, CREAM = "#1A1A14", "#26261E", "#F2EFE2"
SUN, SUN_DK, SUN_LT = "#C6986B", "#8A5E35", "#EEDDC7"
WARN = "#B5533C"

W, H = config.frame_width, config.frame_height
LEFT_X, RIGHT_X = -W / 2 + 0.7, W / 2 - 0.7

LATIN = "Readex Pro"
ARABIC = "Noto Naskh Arabic"
ARABIC_DISPLAY = "Amiri"


TEXT_SCALE = 0.8   # deck sizes are written in "slide points"; Manim's own font_size runs ~1.4x larger
SUPER = 4           # render glyphs at 4x and scale down: avoids uneven letter spacing at small sizes


def T(s, size=28, color=INK, weight=NORMAL, **kw):
    t = Text(s, font=LATIN, font_size=size * TEXT_SCALE * SUPER, color=color, weight=weight, **kw)
    return t.scale(1 / SUPER)


def A(s, size=40, color=INK, font=ARABIC):
    # MarkupText, not Text: Text silently drops single Arabic words (see SPIKE_NOTES.md)
    return MarkupText(s, font=font, font_size=size * TEXT_SCALE * SUPER, color=color).scale(1 / SUPER)


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


class Deck(Slide):
    """One scene = one slide; self.next_slide() marks a click. Subclasses set NUM, KICKER, TITLE and override build()."""
    NUM, KICKER, TITLE = 0, "", ""
    DARK = False
    TOTAL = 9

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
        self.add(foot)
        self.header = VGroup(*items)
        return self.header

    def construct(self):
        header = self.chrome()
        if len(header):
            self.play(FadeIn(header, shift=RIGHT * 0.3), run_time=0.7)
        self.build()
        self.wait(1.5)

    def build(self):
        raise NotImplementedError
