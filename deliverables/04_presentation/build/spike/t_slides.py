from manim import *
from manim_slides import Slide
PAPER="#F6F2E6"; INK="#282824"; SUN="#C6986B"
class T(Slide):
    def construct(self):
        self.camera.background_color = ManimColor(PAPER)
        w = MarkupText("كتب", font="Amiri", color=INK).scale(3)
        self.play(Write(w)); self.next_slide()
        outs = VGroup(*[MarkupText(t, font="Amiri", color=INK).scale(1.2) for t in ["كَتَبَ","كُتِبَ","كُتُب"]]).arrange(RIGHT, buff=1)
        self.play(ReplacementTransform(w, outs)); self.play(Indicate(outs[0], color=SUN))
        self.next_slide()
