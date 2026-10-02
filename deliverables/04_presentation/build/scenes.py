"""The nine slides of the Bayan pitch (idea -> verdict -> data -> training). One Scene class per slide.

Every number comes from Bayan_Final_Report.pdf (28 Sep 2026) or docs/decisions/0001-product-form.md.
Render one:  manim render -ql scenes.py S2Problem      (see build.sh for the full pipeline)
"""
from common import *


# ---------------------------------------------------------------- 1. cover
class S1Cover(Deck):
    NUM, DARK = 1, True

    def build(self):
        mark = svg("bayan-mark-dark.svg", width=3.6).move_to([0, 1.55, 0])
        ink, dot = mark[0], mark[1]
        title = T("Bayan", 72, CREAM, SEMIBOLD).next_to(mark, DOWN, buff=0.35)
        sub = T("On-device Arabic text simplification for readers with dyslexia", 24, CREAM).next_to(title, DOWN, buff=0.3)
        team = T("Team Cogni", 22, SUN, MEDIUM).next_to(sub, DOWN, buff=0.55)
        names = T("Marwan Elamami · Abdulrahman Khengari · Ahmed Alaeb · Sanad Ali · Mohammed Thabet · Abdul Majid Mraied",
                  13, INK4).next_to(team, DOWN, buff=0.2)
        names.scale_to_fit_width(min(names.width, W - 1.6))
        self.play(Create(ink, run_time=2.2), FadeIn(dot, scale=0.2, run_time=1.4))
        self.play(dot.animate.scale(1.5), rate_func=there_and_back, run_time=0.8)
        self.play(FadeIn(title, shift=UP * 0.2), run_time=0.7)
        self.play(FadeIn(sub, shift=UP * 0.2), run_time=0.7)
        self.play(FadeIn(team), FadeIn(names), run_time=0.8)


# ---------------------------------------------------------------- 2. the problem
class S2Problem(Deck):
    NUM, KICKER, TITLE = 2, "01 · The idea", "Arabic hides its own pronunciation"

    def build(self):
        # left: prevalence
        num = DecimalNumber(0, num_decimal_places=0, unit="\\%", font_size=120, color=SUN)
        num.set_color(SUN)
        num.move_to([-3.35, 0.7, 0])
        lab = T("of Arab primary-school children\nhave developmental dyslexia", 22, INK2, line_spacing=0.9)
        lab.next_to(num, DOWN, buff=0.3)
        src = T("pooled over 18 studies, N = 30,243", 15, INK3).next_to(lab, DOWN, buff=0.2)
        self.add(num)
        self.play(ChangeDecimalToValue(num, 11, run_time=1.6, rate_func=rush_from))
        self.play(FadeIn(lab, shift=UP * 0.15), FadeIn(src), run_time=0.7)
        self.next_slide()

        # right: one written form, three readings
        panel = card(5.5, 3.75).move_to([2.55, 0.28, 0])
        word = A("كتب", 100, INK, ARABIC_DISPLAY).move_to(panel.get_top() + DOWN * 0.95)
        cap = T("one written form", 15, INK3).next_to(word, DOWN, buff=0.15)
        self.play(FadeIn(panel), Write(word), FadeIn(cap), run_time=1.0)
        rows = VGroup()
        for ar, tr, en in [("كَتَبَ", "kataba", "he wrote"), ("كُتِبَ", "kutiba", "it was written"), ("كُتُب", "kutub", "books")]:
            a = A(ar, 44, INK, ARABIC_DISPLAY)
            t = T(f"{tr} · {en}", 16, SUN_DK)
            col = VGroup(a, t).arrange(DOWN, buff=0.12)
            rows.add(col)
        rows.arrange(LEFT, buff=0.22).move_to(panel.get_bottom() + UP * 0.95)
        arrows = VGroup(*[Arrow(cap.get_bottom(), r.get_top() + UP * 0.05, buff=0.12, color=SUN, stroke_width=3,
                                max_tip_length_to_length_ratio=0.25) for r in rows])
        self.play(LaggedStart(*[AnimationGroup(GrowArrow(a), FadeIn(r, shift=DOWN * 0.15)) for a, r in zip(arrows, rows)],
                              lag_ratio=0.35, run_time=1.6))

        self.next_slide()
        # bottom: the other two barriers
        c1 = chip("Fused prefixes and suffixes  →  long words that resist chunking", fill=PAPER2, color=INK2, size=17)
        c2 = chip("Clauses chained with و and ف  →  sentences longer than working memory", fill=PAPER2, color=INK2, size=17)
        for c in (c1, c2):
            c.scale_to_fit_width(min(c.width, W - 1.4))
        both = VGroup(c1, c2).arrange(DOWN, buff=0.2, aligned_edge=LEFT).move_to([LEFT_X, -2.5, 0], aligned_edge=LEFT)
        self.play(LaggedStart(FadeIn(c1, shift=UP * 0.15), FadeIn(c2, shift=UP * 0.15), lag_ratio=0.4, run_time=1.2))


# ---------------------------------------------------------------- 3. the gap
class S3Gap(Deck):
    NUM, KICKER, TITLE = 3, "01 · The idea", "Nobody had built this: no tool, no data"

    def build(self):
        cols = ["SAMER", "BAREC", "Baseet", "DAASI"]
        rows = [
            ("Rewrites by", ["human", "none (levels only)", "LLM", "human-verified"]),
            ("Adds a sentence", ["0% of pairs", "n/a", "2–4%", "8%"]),
            ("Made for dyslexia", ["no", "no", "no", "no"]),
        ]
        x0, cw, rh = -1.6, 2.1, 0.85
        y0 = 1.3
        head = VGroup(*[T(c, 24, INK, SEMIBOLD).move_to([x0 + i * cw, y0, 0]) for i, c in enumerate(cols)])
        sub = VGroup(*[T(s, 14, INK3).next_to(h, DOWN, buff=0.08) for h, s in zip(head, [
            "15 novels, 3 levels", "69,441 sentences", "3 LLM levels", "gov. & insurance text"])])
        self.play(FadeIn(head, shift=DOWN * 0.15), FadeIn(sub), run_time=0.8)
        rule = Line([LEFT_X, y0 - 0.55, 0], [RIGHT_X, y0 - 0.55, 0], color=PAPER3, stroke_width=2)
        self.play(Create(rule), run_time=0.4)
        for r, (name, vals) in enumerate(rows):
            y = y0 - 1.15 - r * rh
            last = r == len(rows) - 1
            if last:
                self.next_slide()
            lab = T(name, 20, WARN if last else INK2, SEMIBOLD if last else MEDIUM).move_to([LEFT_X, y, 0], aligned_edge=LEFT)
            cells = VGroup(*[T(v, 20, WARN if last else INK2, MEDIUM if last else NORMAL).move_to([x0 + i * cw, y, 0])
                             for i, v in enumerate(vals)])
            anims = [FadeIn(lab, shift=RIGHT * 0.15), *[FadeIn(c, shift=UP * 0.1) for c in cells]]
            if last:
                band = card(W - 1.2, 0.8, fill="#F3E2DA", stroke="#F3E2DA", r=0.15).move_to([0, y, 0])
                anims.insert(0, FadeIn(band))
                self.add(band)
                self.bring_to_back(band)
            self.play(LaggedStart(*anims, lag_ratio=0.08, run_time=1.0))
        self.next_slide()
        gap = T("No deployed Arabic dyslexia tool simplifies text, and no open corpus teaches splitting.", 18, INK2)
        gap.move_to([0, -2.5, 0])
        gap.scale_to_fit_width(min(gap.width, W - 1.4))
        plan = VGroup(sun(0.11), T("So we built our own data, our own models and our own benchmark.", 22, INK, SEMIBOLD))
        plan[1].scale_to_fit_width(min(plan[1].width, W - 2.0))
        plan.arrange(RIGHT, buff=0.25).move_to([0, -3.0, 0])
        self.play(FadeIn(gap, shift=UP * 0.1), run_time=0.7)
        self.play(FadeIn(plan, shift=UP * 0.15), run_time=0.8)


# ---------------------------------------------------------------- 4. the verdict
class S4Verdict(Deck):
    NUM, KICKER, TITLE = 4, "02 · The verdict", "Simplify where the reader already is"

    def build(self):
        q = T("Where does a reader meet hard Arabic?  Inside other apps.", 19, INK2).next_to(self.header, DOWN, buff=0.35, aligned_edge=LEFT)
        at_left(q)
        self.play(FadeIn(q), run_time=0.6)
        opts = VGroup()
        for tag, name, why in [("A", "Chrome extension", "desktop-first; reading happens on the phone"),
                               ("B", "Android plugin", "«تبسيط» in the selection menu of every app"),
                               ("C", "Standalone app", "copy, paste, leave the app: the friction we remove")]:
            box = card(5.2, 1.05)
            badge = VGroup(Circle(0.27, fill_color=INK4, fill_opacity=1, stroke_width=0), T(tag, 22, PAPER, SEMIBOLD))
            badge[1].move_to(badge[0])
            nm = T(name, 22, INK, SEMIBOLD)
            ws = T(why, 14, INK3) if tag != "B" else T("‘تبسيط’ in the selection menu of every app", 14, INK3)
            txt = VGroup(nm, ws).arrange(DOWN, buff=0.08, aligned_edge=LEFT)
            row = VGroup(box, badge, txt)
            badge.move_to(box.get_left() + RIGHT * 0.55)
            txt.next_to(badge, RIGHT, buff=0.3)
            opts.add(row)
        opts.arrange(DOWN, buff=0.22).move_to([-2.8, -0.2, 0])
        self.play(LaggedStart(*[FadeIn(o, shift=RIGHT * 0.25) for o in opts], lag_ratio=0.25, run_time=1.2))

        self.next_slide()
        # phone demo on the right
        ph = RoundedRectangle(width=2.75, height=4.9, corner_radius=0.3, fill_color=PAPER, fill_opacity=1,
                              stroke_color=INK, stroke_width=4).move_to([3.4, -0.35, 0])
        lines = VGroup(*[RoundedRectangle(width=w, height=0.13, corner_radius=0.06, fill_color=PAPER3, fill_opacity=1,
                                          stroke_width=0) for w in [2.0, 2.2, 1.9, 2.2, 1.5, 2.2, 2.0]])
        lines.arrange(DOWN, buff=0.22, aligned_edge=RIGHT).move_to(ph.get_top() + DOWN * 1.45)
        self.play(FadeIn(ph), FadeIn(lines), run_time=0.8)
        sel = VGroup(*[RoundedRectangle(width=l.width, height=0.17, corner_radius=0.06, fill_color=SUN, fill_opacity=0.55,
                                        stroke_width=0).move_to(l) for l in lines[2:5]])
        self.play(LaggedStart(*[Create(s) for s in sel], lag_ratio=0.3, run_time=0.9))
        menu = card(2.05, 0.6, fill="#FFFFFF", stroke=PAPER3, r=0.14)
        items = VGroup(T("Copy", 13, INK3), A("تبسيط", 22, SUN_DK, ARABIC), T("Share", 13, INK3)).arrange(RIGHT, buff=0.22)
        pop = VGroup(menu, items.move_to(menu)).move_to(sel.get_top() + UP * 0.5)
        self.play(FadeIn(pop, shift=UP * 0.15, scale=0.9), run_time=0.6)
        self.play(Indicate(items[1], color=SUN, scale_factor=1.15), run_time=0.7)
        sheet = RoundedRectangle(width=2.5, height=2.2, corner_radius=0.22, fill_color=PAPER2, fill_opacity=1,
                                 stroke_color=INK4, stroke_width=2)
        handle = RoundedRectangle(width=0.5, height=0.07, corner_radius=0.03, fill_color=INK4, fill_opacity=1, stroke_width=0)
        out_lines = VGroup(*[RoundedRectangle(width=w, height=0.13, corner_radius=0.06, fill_color=SUN, fill_opacity=0.8,
                                              stroke_width=0) for w in [2.0, 1.7, 1.9]]).arrange(DOWN, buff=0.2, aligned_edge=RIGHT)
        play = VGroup(Circle(0.2, fill_color=SUN, fill_opacity=1, stroke_width=0),
                      Triangle(fill_color=PAPER, fill_opacity=1, stroke_width=0).scale(0.09).rotate(-PI / 2))
        play[1].move_to(play[0]).shift(RIGHT * 0.02)
        content = VGroup(handle, out_lines, play).arrange(DOWN, buff=0.25)
        play.align_to(out_lines, LEFT)
        content.move_to(sheet)
        group = VGroup(sheet, content)
        group.move_to(ph.get_bottom() + UP * 1.3)
        self.play(FadeOut(pop), FadeIn(group, shift=UP * 0.9), run_time=0.9)
        self.next_slide()
        # verdict: dim A and C, light up B
        b = opts[1]
        ring = SurroundingRectangle(b[0], color=SUN, buff=0.0, corner_radius=0.18, stroke_width=5)
        for o in (opts[0], opts[2]):
            o.generate_target()
        self.play(opts[0].animate.set_opacity(0.35), opts[2].animate.set_opacity(0.35),
                  b[1][0].animate.set_fill(SUN), Create(ring), run_time=0.9)
        r1 = VGroup(chip("on-device", size=17), chip("offline", size=17), chip("≤ 250 MB", size=17)).arrange(RIGHT, buff=0.15)
        r2 = chip("the reader’s text never leaves the phone", size=17)
        foot = VGroup(r1, r2).arrange(DOWN, buff=0.15, aligned_edge=LEFT).move_to([-2.75, -2.75, 0])
        at_left(foot)
        self.play(LaggedStart(*[FadeIn(f, shift=UP * 0.1) for f in foot], lag_ratio=0.15, run_time=0.9))


# ---------------------------------------------------------------- 5. data
class S5Data(Deck):
    NUM, KICKER, TITLE = 5, "03 · Data", "Audit first, then build the training set"

    def build(self):
        big = T("9.3%", 84, WARN, SEMIBOLD).move_to([LEFT_X + 1.5, 1.45, 0])
        txt = T("of Baseet overlapped our locked test sets.\nEvery training file now passes a leakage gate.", 22, INK2,
                line_spacing=0.95).next_to(big, RIGHT, buff=0.5)
        self.play(FadeIn(big, scale=1.3), run_time=0.7)
        self.play(FadeIn(txt, shift=LEFT * 0.2), run_time=0.8)
        self.next_slide()

        total = 22733
        segs = [("[S0]", "14,343", "SAMER · 6,033 unchanged kept", INK, CREAM),
                ("[S1]", "3,508", "Baseet · light", SUN_DK, CREAM),
                ("[S2]", "1,954", "Baseet · medium", SUN, INK),
                ("[S3]", "1,426", "Baseet · strong", "#DDBB95", INK),
                ("[SA]", "1,502", "DAASI · everyday", INK3, CREAM)]
        bw, y, x = W - 1.4, -0.35, LEFT_X
        title = T("22,733 training pairs, every one tagged with its source style", 20, INK, SEMIBOLD)
        title.move_to([LEFT_X, y + 0.85, 0], aligned_edge=LEFT)
        self.play(FadeIn(title))
        bar, tags = VGroup(), VGroup()
        for tag, n, _, col, fg in segs:
            w = bw * int(n.replace(",", "")) / total
            r = Rectangle(width=w, height=0.8, fill_color=col, fill_opacity=1, stroke_color=PAPER, stroke_width=3)
            r.move_to([x + w / 2, y, 0])
            x += w
            t = T(tag, 18, fg, SEMIBOLD)
            t.scale_to_fit_width(min(t.width, w - 0.15)).move_to(r)
            bar.add(r)
            tags.add(t)
        self.play(LaggedStart(*[AnimationGroup(GrowFromEdge(r, LEFT), FadeIn(t)) for r, t in zip(bar, tags)],
                              lag_ratio=0.3, run_time=2.0))
        # legend: five even columns
        colw = bw / 5
        leg = VGroup()
        for i, (tag, n, note, col, _) in enumerate(segs):
            sw = Square(0.16, fill_color=col, fill_opacity=1, stroke_width=0)
            a = T(n, 22, INK, SEMIBOLD)
            b = T(note, 14, INK3)
            b.scale_to_fit_width(min(b.width, colw - 0.2))
            col_g = VGroup(VGroup(sw, a).arrange(RIGHT, buff=0.12), b).arrange(DOWN, buff=0.08, aligned_edge=LEFT)
            col_g.move_to([LEFT_X + colw * i, y - 1.05, 0], aligned_edge=LEFT)
            leg.add(col_g)
        self.play(LaggedStart(*[FadeIn(g, shift=UP * 0.1) for g in leg], lag_ratio=0.15, run_time=1.0))
        self.next_slide()
        gate = VGroup(sun(0.1), T("Baseet pairs pass a meaning filter:  LaBSE ≥ 0.646  ·  length ≥ 67% of source  ·  every number kept",
                                  16, INK2))
        gate[1].scale_to_fit_width(min(gate[1].width, W - 1.9))
        gate.arrange(RIGHT, buff=0.2).move_to([0, -2.75, 0])
        gate2 = T("each threshold = 5th percentile of human-verified rewrites (DAASI)", 14, INK3).next_to(gate, DOWN, buff=0.14)
        self.play(FadeIn(gate, shift=UP * 0.1), FadeIn(gate2), run_time=0.9)


# ---------------------------------------------------------------- 6. training: two candidates
class S6Candidates(Deck):
    NUM, KICKER, TITLE = 6, "04 · Training", "Two candidates, one recipe"

    def build(self):
        recipe = card(W - 1.4, 1.05).move_to([0, 1.2, 0])
        head = T("one script (train.py)  ·  identical data  ·  architecture is the only difference", 19, INK, SEMIBOLD)
        head.scale_to_fit_width(min(head.width, W - 2.0))
        head.move_to(recipe.get_top() + DOWN * 0.3)
        chips = VGroup(*[chip(c, fill=PAPER, color=INK2, size=14, padx=0.22, pady=0.1) for c in
                         ["10 epochs", "fp16", "seed 42", "max length 256", "best SARI on changed rows"]])
        chips.arrange(RIGHT, buff=0.15).move_to(recipe.get_bottom() + UP * 0.33)
        self.play(FadeIn(recipe), FadeIn(head), run_time=0.7)
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.1) for c in chips], lag_ratio=0.12, run_time=0.9))

        self.next_slide()
        maxw = 5.4
        specs = [("AraT5v2", 368, INK, "368M params  ·  won Baseet’s head-to-head  ·  models 1 & 2", False),
                 ("AraBART", 139, SUN, "139M params  ·  2.6× smaller  ·  the on-device contender", False),
                 ("HPLT T5", 294, INK4, "≈ 294M params  ·  held in reserve", True)]
        y = -0.2
        for name, m, col, note, dashed in specs:
            n = T(name, 22, INK, SEMIBOLD).move_to([LEFT_X, y, 0], aligned_edge=LEFT)
            w = maxw * m / 368
            r = Rectangle(width=w, height=0.5, fill_color=col, fill_opacity=0.25 if dashed else 1, stroke_color=col,
                          stroke_width=3).move_to([LEFT_X + 1.85 + w / 2, y, 0])
            nt = T(note, 16, INK3).next_to(r, DOWN, buff=0.1, aligned_edge=LEFT)
            self.play(FadeIn(n), GrowFromEdge(r, LEFT), run_time=0.7)
            self.play(FadeIn(nt), run_time=0.4)
            y -= 0.95
        self.next_slide()
        # the size story: 46% of AraT5v2 is two embedding tables
        tail = VGroup(sun(0.1), T("46% of AraT5v2 is two embedding tables, so shrinking its vocabulary is the route to phone size.", 15, INK2))
        tail[1].scale_to_fit_width(min(tail[1].width, W - 1.9))
        tail.arrange(RIGHT, buff=0.2).move_to([0, -3.0, 0])
        self.play(FadeIn(tail, shift=UP * 0.1), run_time=0.7)


# ---------------------------------------------------------------- 7. model 1
class S7Model1(Deck):
    NUM, KICKER, TITLE = 7, "04 · Training", "Model 1: the score that looked like a failure"

    def build(self):
        ax_x, ax_y, ax_w, ax_h = -3.9, -2.3, 5.4, 3.5
        base = Line([ax_x, ax_y, 0], [ax_x + ax_w, ax_y, 0], color=INK4, stroke_width=3)

        def bars(vals, ymax=100):
            out = VGroup()
            for i, (label, v, col) in enumerate(vals):
                h = ax_h * v / ymax
                r = Rectangle(width=1.5, height=h, fill_color=col, fill_opacity=1, stroke_width=0)
                r.move_to([ax_x + 1.35 + i * 2.5, ax_y + h / 2, 0])
                val = T(f"{v:.2f}", 24, INK, SEMIBOLD).next_to(r, UP, buff=0.12)
                lab = T(label, 17, INK2).next_to(r, DOWN, buff=0.15)
                out.add(VGroup(r, val, lab))
            return out

        def fmt(title, sub):
            a = T(title, 22, INK, SEMIBOLD)
            b = T(sub, 14, INK3)
            return VGroup(a, b).arrange(DOWN, buff=0.06, aligned_edge=LEFT)

        t1 = fmt("SARI on all SAMER test rows", "3,277 sentences, half need no change").move_to([ax_x, 1.5, 0], aligned_edge=LEFT)
        b1 = bars([("copy the input", 77.50, INK4), ("Model 1", 75.88, SUN)])
        self.play(Create(base), FadeIn(t1), run_time=0.6)
        self.play(LaggedStart(*[GrowFromEdge(b, DOWN) for b in b1], lag_ratio=0.3, run_time=1.2))
        # right column: the verdict on the first view
        v1 = T("Copying wins?", 30, WARN, SEMIBOLD).move_to([3.0, 0.9, 0])
        why = T("Half of SAMER needs no change,\nso doing nothing scores well.", 19, INK2, line_spacing=0.95).next_to(v1, DOWN, buff=0.2)
        self.play(FadeIn(v1, shift=LEFT * 0.2), FadeIn(why), run_time=0.8)
        self.next_slide()
        # flip to the honest view
        t2 = fmt("SARI on rows a human changed", "1,678 sentences: the bar a model must clear").move_to([ax_x, 1.5, 0], aligned_edge=LEFT)
        b2 = bars([("copy the input", 56.06, INK4), ("Model 1", 61.83, SUN)])
        v2 = T("Model 1 clears it", 30, SUN_DK, SEMIBOLD).move_to(v1)
        why2 = T("+5.8 points, greedy decoding:\nwhat the phone runs.", 19, INK2, line_spacing=0.95).next_to(v2, DOWN, buff=0.2)
        self.play(FadeOut(b1, t1, v1, why), run_time=0.5)
        self.play(FadeIn(t2), LaggedStart(*[GrowFromEdge(b, DOWN) for b in b2], lag_ratio=0.3, run_time=1.1))
        self.play(FadeIn(v2, shift=LEFT * 0.2), FadeIn(why2), run_time=0.8)
        note = T("But it made mostly one-word edits, and 42% of its training pairs were unchanged sentences.", 17, INK3)
        note.scale_to_fit_width(min(note.width, W - 1.4)).move_to([0, -3.15, 0])
        self.play(FadeIn(note, shift=UP * 0.1), run_time=0.7)


# ---------------------------------------------------------------- 8. model 2
class S8Model2(Deck):
    NUM, KICKER, TITLE = 8, "04 · Training", "Model 2: one fix for each lesson"

    def build(self):
        items = [
            ("It rewards doing nothing", "Keep all 6,033 unchanged pairs;\npick the checkpoint on changed rows only"),
            ("SAMER is novels: it teaches word swaps", "Add DAASI (everyday, admin) and Baseet\n(educational) through a meaning filter"),
            ("One strength fits no one", "A strength tag on every source;\nat run time it is the app’s strength setting"),
        ]
        y = 1.65
        for i, (prob, fix) in enumerate(items):
            if i:
                self.next_slide()
            p = card(3.6, 1.05, fill="#F3E2DA", stroke="#F3E2DA").move_to([LEFT_X + 1.8, y, 0])
            pt = T(prob, 19, WARN, MEDIUM, line_spacing=0.9)
            pt.scale_to_fit_width(min(pt.width, 3.2)).move_to(p)
            ar = Arrow(p.get_right(), p.get_right() + RIGHT * 0.65, buff=0.08, color=SUN, stroke_width=4)
            f = card(5.3, 1.05, fill=PAPER2, stroke=PAPER3).move_to([RIGHT_X - 2.65, y, 0])
            ft = T(fix, 17, INK2, line_spacing=0.9)
            ft.scale_to_fit_width(min(ft.width, 4.8)).move_to(f)
            num = T(f"{i + 1}", 22, SUN, SEMIBOLD).move_to(p.get_left() + LEFT * 0.0 + RIGHT * 0.3)
            self.play(FadeIn(p), FadeIn(pt), run_time=0.45)
            self.play(GrowArrow(ar), FadeIn(f, shift=LEFT * 0.2), FadeIn(ft), run_time=0.7)
            y -= 1.3
        self.next_slide()
        tags = [("[S0]", "minimal"), ("[S1]", "light"), ("[S2]", "medium · default"), ("[S3]", "strong"), ("[SA]", "everyday")]
        tg = VGroup()
        for t, m in tags:
            a = T(t, 22, INK, SEMIBOLD)
            b = T(m, 13, INK3)
            box = card(1.85, 0.95, fill=PAPER, stroke=SUN, r=0.15)
            VGroup(a, b).arrange(DOWN, buff=0.07).move_to(box)
            tg.add(VGroup(box, a, b))
        tg.arrange(RIGHT, buff=0.15).scale_to_fit_width(W - 1.4).move_to([0, -2.85, 0])
        self.play(LaggedStart(*[FadeIn(t, shift=UP * 0.15) for t in tg], lag_ratio=0.12, run_time=1.0))
        cur = sun(0.12).move_to(tg[0].get_top() + UP * 0.25)
        self.play(FadeIn(cur), run_time=0.3)
        for t in tg[1:]:
            self.play(cur.animate.move_to(t.get_top() + UP * 0.25), t[0].animate.set_fill(SUN_LT), run_time=0.45)


# ---------------------------------------------------------------- 9. close
class S9Close(Deck):
    NUM, DARK = 9, True

    def build(self):
        logo = svg("bayan-horizontal-dark.svg", width=4.2).move_to([0, 1.75, 0])
        line = T("Simplify where you read.", 40, CREAM, SEMIBOLD).next_to(logo, DOWN, buff=0.55)
        nxt = T("Next: does it work?", 22, SUN, MEDIUM).next_to(line, DOWN, buff=0.7)
        pts = VGroup(*[chip(t, fill=NIGHT2, color=CREAM, size=17) for t in
                       ["BayanBench: a benchmark for the reader’s task", "On a real phone", "Readers with dyslexia"]])
        pts.arrange(RIGHT, buff=0.2)
        pts.scale_to_fit_width(min(pts.width, W - 1.4)).next_to(nxt, DOWN, buff=0.3)
        self.play(FadeIn(logo, shift=UP * 0.2), run_time=0.9)
        self.play(FadeIn(line, shift=UP * 0.2), run_time=0.8)
        self.next_slide()
        self.play(FadeIn(nxt), LaggedStart(*[FadeIn(p, shift=UP * 0.1) for p in pts], lag_ratio=0.2), run_time=1.2)
        slogan = ImageMobject(str(ASSETS / "sic-slogan-white.png")).scale_to_fit_width(1.9).move_to([0, -2.9, 0])
        self.play(FadeIn(slogan), run_time=0.7)
