from manim import constants; constants.FFMPEG_BIN = "ffmpeg"
from manim import *
from manim_pptx import *
PAPER="#F6F2E6"; INK="#282824"; SUN="#C6986B"
class T(PPTXScene):
    def construct(self):
        self.camera.background_color = ManimColor(PAPER)
        w = MarkupText("كتب", font="Amiri", color=INK).scale(3)
        self.play(Write(w)); self.endSlide()
        outs = VGroup(*[MarkupText(t, font="Amiri", color=INK).scale(1.2) for t in ["كَتَبَ","كُتِبَ","كُتُب"]]).arrange(RIGHT, buff=1)
        self.play(ReplacementTransform(w, outs)); self.play(Indicate(outs[0], color=SUN))
        self.endSlide()
