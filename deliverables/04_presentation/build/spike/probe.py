from manim import *
class P(Scene):
    def construct(self):
        self.camera.background_color = ManimColor("#F6F2E6")
        m = SVGMobject("../assets/bayan-mark-light.svg").scale_to_fit_width(4)
        print("logo",len(m.submobjects), [str(c.get_fill_color()) for c in m.submobjects[:3]])
        s = SVGMobject("../assets/samsung-blue.svg").scale_to_fit_width(2).to_corner(UL)
        t = Text("Readex Pro test 11%", font="Readex Pro", weight=SEMIBOLD, color="#282824").to_edge(DOWN)
        self.add(m,s,t)
