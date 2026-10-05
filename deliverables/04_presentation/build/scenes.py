"""The eight beats of the Bayan pitch (problem -> data -> models -> measuring -> results -> phone -> close).

One Scene class per beat. Within a beat the steps advance on their own and the beat stops at
its end — `begin_beat()` and `step()` in `common.Deck`. That is "stop at certain points
automatically".

Every number is imported from `facts.py`; `check_numbers.py` refuses to let unsourced figures
into the deck. Render with `./render_videos.sh`.
"""
from common import *
from facts import FIG


def F(key):
    return FIG[key][0]


def R(x):
    """Round half up, for numbers shown on a slide (the exact value stays in facts.py)."""
    return int(x + 0.5)


TOTAL = 8


# ---------------------------------------------------------------- 1. cover
class S1Cover(Deck):
    NUM, DARK, TOTAL = 1, True, TOTAL

    def build(self):
        mark = svg("bayan-mark-dark.svg", width=3.4).move_to([0, 1.75, 0])
        ink, dot = mark[0], mark[1]
        title = T("Bayan", 72, CREAM, SEMIBOLD).next_to(mark, DOWN, buff=0.35)
        sub = T("Simplify Arabic where you read", 26, CREAM).next_to(title, DOWN, buff=0.28)
        tag = T("on the phone, offline", 18, SUN).next_to(sub, DOWN, buff=0.16)
        team = T("Team Cogni", 22, SUN, MEDIUM).next_to(tag, DOWN, buff=0.5)
        names = T("Marwan Elamami · Abdulrahman Khengari · Ahmed Alaeb · Sanad Ali · "
                  "Mohammed Thabet · Abdul Majid Mraied", 13, INK4).next_to(team, DOWN, buff=0.2)
        names.scale_to_fit_width(min(names.width, W - 1.6))
        self.play(Create(ink, run_time=2.0), FadeIn(dot, scale=0.2, run_time=1.3))
        self.play(dot.animate.scale(1.5), rate_func=there_and_back, run_time=0.7)
        self.play(FadeIn(title, shift=UP * 0.2), FadeIn(sub, shift=UP * 0.2), run_time=0.7)
        self.play(FadeIn(tag), FadeIn(team), FadeIn(names), run_time=0.8)


# ---------------------------------------------------------------- 2. the problem
class S2Problem(Deck):
    NUM, KICKER, TITLE, TOTAL = 2, "01 · The problem", "Reading in Arabic adds load", TOTAL

    def build(self):
        self.begin_beat()

        # step 1: prevalence, then one written form with three readings
        num = DecimalNumber(0, num_decimal_places=0, unit="\\%", font_size=110, color=SUN)
        num.move_to([-3.3, 0.85, 0])
        lab = T("of Arab primary-school children\nhave developmental dyslexia", 22, INK2, line_spacing=0.9)
        lab.next_to(num, DOWN, buff=0.3)
        src = source_badge(f"Al-Dakhil 2024 · {F('dyslexia_studies')} studies, N = {F('dyslexia_n'):,}")
        src.next_to(lab, DOWN, buff=0.3, aligned_edge=LEFT)
        left = VGroup(num, lab, src)
        self.add(num)
        self.play(ChangeDecimalToValue(num, F("dyslexia_pct"), run_time=1.5, rate_func=rush_from))
        self.play(FadeIn(lab, shift=UP * 0.15), FadeIn(src), run_time=0.6)

        panel = card(5.0, 3.9).move_to([2.55, 0.2, 0])
        word = A("كتب", 100, INK, ARABIC_DISPLAY).move_to(panel.get_top() + DOWN * 0.95)
        cap = T("one written form", 15, INK3).next_to(word, DOWN, buff=0.12)
        self.play(FadeIn(panel), Write(word), FadeIn(cap), run_time=0.9)
        rows = VGroup()
        for ar, tr, en in [("كَتَبَ", "kataba", "he wrote"),
                           ("كُتِبَ", "kutiba", "it was written"),
                           ("كُتُب", "kutub", "books")]:
            rows.add(VGroup(A(ar, 40, INK, ARABIC_DISPLAY), T(tr, 15, SUN_DK, MEDIUM), T(en, 13, INK3))
                     .arrange(DOWN, buff=0.06))
        rows.arrange(RIGHT, buff=0.35).move_to(panel.get_bottom() + UP * 0.95)
        arrows = VGroup(*[Arrow(cap.get_bottom(), r.get_top() + UP * 0.05, buff=0.12, color=SUN,
                                stroke_width=3, max_tip_length_to_length_ratio=0.25) for r in rows])
        self.play(LaggedStart(*[AnimationGroup(GrowArrow(a), FadeIn(r, shift=DOWN * 0.15))
                                for a, r in zip(arrows, rows)], lag_ratio=0.35, run_time=1.5))
        step1 = VGroup(left, panel, word, cap, rows, arrows)
        self.hold()

        # step 2: what helps, and our scope
        helps = card(4.6, 3.3).move_to([-2.6, 0.1, 0])
        h_t = T("What helps", 20, INK, SEMIBOLD).move_to(helps.get_top() + DOWN * 0.45)
        h_b = fit(T("Splitting long clauses into\nshort sentences: read faster,\nunderstood better, most by\nthe weakest readers.",
                    16, INK2, line_spacing=0.95), 4.2).next_to(h_t, DOWN, buff=0.3)
        h_s = source_badge("Javourey-Bonnet 2022").move_to(helps.get_bottom() + UP * 0.4)
        scope = card(4.6, 3.3, fill=SUN_LT, stroke=SUN).move_to([2.6, 0.1, 0])
        s_t = T("Bayan's scope", 20, SUN_DK, SEMIBOLD).move_to(scope.get_top() + DOWN * 0.45)
        s_a = chip("we reduce reading load", fill=PAPER, color=SUN_DK, size=16, weight=SEMIBOLD)
        s_b = chip("long clauses · hard words", fill=PAPER, color=INK2, size=15)
        s_c = chip("not decoding · no reader claim yet", fill=WARN_LT, color=WARN, size=14)
        s_all = fit(VGroup(s_a, s_b, s_c).arrange(DOWN, buff=0.22), 4.2).move_to(scope.get_center() + DOWN * 0.35)
        self.play(FadeOut(step1), run_time=0.5)
        self.play(FadeIn(helps), FadeIn(h_t), FadeIn(scope), FadeIn(s_t), run_time=0.7)
        self.play(FadeIn(h_b), FadeIn(h_s), LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in s_all],
                                                        lag_ratio=0.3), run_time=1.3)


# ---------------------------------------------------------------- 3. data processing
class S3Data(Deck):
    NUM, KICKER, TITLE, TOTAL = 3, "02 · Data", "How we got to corpus v1", TOTAL

    def build(self):
        self.begin_beat()

        # step 1: what existed
        def panel(x, title, lines, fill=PAPER2, stroke=PAPER3, tcol=INK):
            c = card(4.6, 3.3, fill=fill, stroke=stroke).move_to([x, 0.1, 0])
            t = T(title, 19, tcol, SEMIBOLD).move_to(c.get_top() + DOWN * 0.45)
            chips = VGroup(*[chip(l, fill=PAPER, color=INK2, size=14) for l in lines]).arrange(DOWN, buff=0.2)
            fit(chips, 4.2).move_to(c.get_center() + DOWN * 0.3)
            return VGroup(c, t, chips)

        a = panel(-2.6, "SAMER · human-written", [
            "novels, short sentences",
            f"{F('samer_identity_lo')}–{F('samer_identity_hi')}% of pairs unchanged",
            f"length ratio {F('samer_ratio'):.2f}: swaps words, never splits"])
        b = panel(2.6, "Other sources · LLM-written", [
            "many targets are summaries",
            "they drop facts, delete options",
            f"after a meaning filter: {F('external_kept'):,} pairs"])
        self.play(FadeIn(a[0]), FadeIn(a[1]), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in a[2]], lag_ratio=0.3, run_time=1.0))
        self.play(FadeIn(b[0]), FadeIn(b[1]), run_time=0.6)
        self.play(LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in b[2]], lag_ratio=0.3, run_time=1.0))
        stage1 = VGroup(a, b)
        self.step()

        # step 2: our own first attempt, corpus v0, and what the audit found
        flow = VGroup(
            chip("DeepSeek: 5 candidates\nper source", fill=PAPER2, color=INK2, size=14),
            chip("LLM equivalence\nvalidator", fill=PAPER2, color=INK2, size=14),
            chip("CAMeL readability\ngate", fill=PAPER2, color=INK2, size=14),
        ).arrange(RIGHT, buff=0.55).move_to([0, 1.55, 0])
        farr = VGroup(*[Arrow(flow[i].get_right(), flow[i + 1].get_left(), buff=0.08, color=SUN, stroke_width=3,
                              max_tip_length_to_length_ratio=0.4) for i in range(2)])
        v0 = T("corpus v0, our first synthetic data", 14, INK3, MEDIUM).next_to(flow, UP, buff=0.18)
        head = T("What the audit found", 18, INK, SEMIBOLD).move_to([LEFT_X, 0.55, 0], aligned_edge=LEFT)
        defects = VGroup(
            chip(f"{R(F('v0_tashkeel'))}% of rows had tashkeel", fill=WARN_LT, color=WARN, size=15),
            chip(f"{R(F('v0_completed'))}% of cut-off sources were simply completed", fill=WARN_LT, color=WARN, size=15),
            chip(f"only {R(F('v0_levels'))}% of pairs were 2+ levels easier", fill=WARN_LT, color=WARN, size=15),
        ).arrange(DOWN, buff=0.12, aligned_edge=LEFT).next_to(head, DOWN, buff=0.2, aligned_edge=LEFT)
        note = chip(f"the validator accepted {R(F('v0_validator_added'))}% of planted added sentences · we trained nothing on v0",
                    fill=PAPER2, color=INK2, size=14)
        fit(note, W - 1.4).move_to([0, -2.4, 0])
        self.play(FadeOut(stage1), run_time=0.5)
        self.play(FadeIn(v0), FadeIn(flow[0]), run_time=0.5)
        self.play(GrowArrow(farr[0]), FadeIn(flow[1]), GrowArrow(farr[1]), FadeIn(flow[2]), run_time=0.9)
        self.play(FadeIn(head), LaggedStart(*[FadeIn(d, shift=RIGHT * 0.15) for d in defects], lag_ratio=0.25,
                                            run_time=1.2))
        self.play(FadeIn(note, shift=UP * 0.1), run_time=0.6)
        stage2 = VGroup(v0, flow, farr, head, defects, note)
        self.step()

        # step 3: so we rebuilt it: source, routing, generation and gates, as two lanes
        self.play(FadeOut(stage2), run_time=0.5)
        left = self._lane("v1 · from the source", [
            ("BAREC train + dev", "test never enters"),
            ("strip tashkeel and tatweel", "every text"),
            ("route each source", f"protected · short · hard  →  {F('route_hard'):,} hard"),
        ]).move_to([-2.5, 0.0, 0])
        right = self._lane("v1 · into the corpus", [
            ("Gemma 4 31B writes candidates", f"hard band only  →  {F('gen_responses'):,} responses"),
            ("code gates", "numbers · quotes · options"),
            ("readability + meaning gates", f"≥ 2 levels · meaning gate  →  {F('accepted_tier_a'):,} accepted"),
        ]).move_to([2.5, 0.0, 0])
        for lane in (left, right):
            self.play(FadeIn(lane[0]), FadeIn(lane[1][0]), run_time=0.4)
            self.play(LaggedStart(*[FadeIn(g, shift=UP * 0.12) for g in lane[1][1:]],
                                  FadeIn(lane[2]), lag_ratio=0.3, run_time=1.0))
        self.hold()

        # step 4: the total and the audit
        arrow = Arrow(left[1].get_right() + UP * 0.9, right[1].get_left() + UP * 0.9, buff=0.1, color=SUN,
                      stroke_width=4, max_tip_length_to_length_ratio=0.5)
        self.play(GrowArrow(arrow), run_time=0.6)
        box = card(4.4, 0.95, fill=SUN_LT, stroke=SUN).move_to([-2.5, -2.3, 0])
        big = T(f"{F('corpus_rows'):,} rows", 28, SUN_DK, SEMIBOLD).move_to(box.get_center() + UP * 0.2)
        sub = T("0 rule violations · 0 leakage vs BAREC test", 13, INK2).next_to(big, DOWN, buff=0.08)
        audit = chip(f"blind audit of {F('audit_n'):,} pairs: {F('audit_changed')}% meaning changed",
                     fill=PAPER2, color=INK2, size=15)
        fit(audit, 4.7).move_to([0.45, -2.3, 0], aligned_edge=LEFT)
        self.play(FadeIn(box, scale=0.9), FadeIn(big), FadeIn(sub), run_time=0.8)
        self.play(FadeIn(audit, shift=UP * 0.12), run_time=0.6)

    def _lane(self, caption, rows):
        """A vertical column of stage cards. Returns VGroup([caption, cards, arrows])."""
        cap = T(caption.upper(), 13, SUN, MEDIUM)
        cards = VGroup()
        for i, (title, sub) in enumerate(rows):
            c = card(4.5, 0.82, fill=PAPER2)
            t = T(title, 17, INK, SEMIBOLD).move_to(c.get_center() + UP * 0.17)
            s = T(sub, 12, INK3).next_to(t, DOWN, buff=0.06)
            fit(t, 4.2)
            fit(s, 4.2)
            cards.add(VGroup(c, t, s).move_to([0, 0.95 - 1.1 * i, 0]))
        arrows = VGroup(*[
            Arrow(cards[i].get_bottom(), cards[i + 1].get_top(), buff=0.03, color=SUN,
                  stroke_width=2.5, max_tip_length_to_length_ratio=0.5)
            for i in range(len(cards) - 1)
        ])
        out = VGroup(cap, cards, arrows)
        cap.next_to(cards, UP, buff=0.2)
        return out


# ---------------------------------------------------------------- 4. the three models
class S4Models(Deck):
    NUM, KICKER, TITLE, TOTAL = 4, "03 · BayanSimplify models", "Each version answered the last failure", TOTAL

    def build(self):
        self.begin_beat()

        cols = VGroup()
        for i, (name, what, data, found) in enumerate([
            ("v0.1", "AraT5v2 on SAMER",
             "SAMER level 5 → 3,\n14,343 pairs",
             f"Returned {R(F('m1_copy_pct'))}% of rows\nunchanged (editors: {R(F('m1_editor_copy_pct'))}%).\nSwapped words, never\nrestructured."),
            ("v0.2", "AraT5v2 (v0.2) and AraBART (v0.2-Fast)",
             "SAMER + everyday text +\nmeaning-filtered pairs + tags",
             f"v0.2 keeps the meaning in\n{R(F('t5_tag_kept'))}% of outputs, v0.2-Fast\nin {R(F('bart_tag_kept'))}%. The tag costs\nmeaning."),
            ("v0.3", "AraT5v2 on corpus v1",
             f"corpus v1, {F('corpus_rows'):,} rows,\nno tag",
             f"Our best: cuts {F('bt_m3_clause')} words from\nthe longest clause vs {F('t5_untag_clause')}, with\nabout the same meaning\n(vs v0.2, no tag)."),
        ]):
            head = card(2.95, 0.6, fill=SUN if i == 2 else PAPER3, stroke=SUN if i == 2 else PAPER3)
            ht = T(name, 20, NIGHT if i == 2 else INK, SEMIBOLD).move_to(head)
            d = card(2.95, 1.05)
            dt = fit(T(data, 14, INK2, line_spacing=0.95), 2.7).move_to(d)
            f = card(2.95, 1.3, fill=WARN_LT, stroke=WARN_LT)
            ft = fit(T(found, 13, WARN, line_spacing=0.95), 2.7, 1.1).move_to(f)
            lbl = T(what, 14 if i == 1 else 13, SUN_DK if i == 1 else INK3, SEMIBOLD if i == 1 else NORMAL)
            fit(lbl, 2.95)
            cols.add(VGroup(lbl, VGroup(head, ht), VGroup(d, dt), VGroup(f, ft)).arrange(DOWN, buff=0.14))
        cols.arrange(RIGHT, buff=0.45).move_to([0, 0.15, 0])

        arrows = VGroup(*[Arrow(cols[i][1].get_right(), cols[i + 1][1].get_left(), buff=0.06, color=SUN,
                                stroke_width=3.5, max_tip_length_to_length_ratio=0.5)
                          for i in range(len(cols) - 1)])

        self.play(FadeIn(cols[0], shift=UP * 0.15), run_time=0.7)
        self.step()
        self.play(GrowArrow(arrows[0]), run_time=0.4)
        self.play(FadeIn(cols[1], shift=UP * 0.15), run_time=0.7)
        self.hold()
        self.play(GrowArrow(arrows[1]), run_time=0.4)
        self.play(FadeIn(cols[2], shift=UP * 0.15), run_time=0.7)
        row = VGroup(
            T("Tried and dropped:", 13, INK3, MEDIUM),
            chip("student DPO", fill=PAPER2, color=INK3, size=12),
            chip("minimum-risk training", fill=PAPER2, color=INK3, size=12),
            chip("fluency retrain", fill=PAPER2, color=INK3, size=12),
        ).arrange(RIGHT, buff=0.25).move_to([0, -2.35, 0])
        self.play(FadeIn(row, shift=UP * 0.1), run_time=0.6)


# ---------------------------------------------------------------- 5. measuring it
class S5Measure(Deck):
    NUM, KICKER, TITLE, TOTAL = 5, "04 · BayanBench", "We checked our own yardstick", TOTAL

    def build(self):
        self.begin_beat()

        # step 1: the copy baseline, and every model against it
        q = fit(T("Copying is the baseline to beat", 26, INK, SEMIBOLD), 6.2)
        q.move_to([LEFT_X, 1.95, 0], aligned_edge=LEFT)
        rows_def = [
            ("Copy the input", 100, 0.0, True),
            ("v0.1", F("bt_m1_kept"), F("bt_m1_clause"), False),
            ("v0.2 (AraT5v2)", F("t5_untag_kept"), F("t5_untag_clause"), False),
            ("v0.2-Fast (AraBART)", F("bart_untag_kept"), F("bart_untag_clause"), False),
            ("v0.3", F("bt_m3_kept"), F("bt_m3_clause"), False),
        ]
        c_name, c_kept, c_cut = -5.0, -1.1, 0.75
        hdr = VGroup(T("meaning kept", 12, INK3, MEDIUM).move_to([c_kept, 1.3, 0]),
                     T("words cut from\nthe longest clause", 12, INK3, MEDIUM, line_spacing=0.9).move_to([c_cut + 0.55, 1.3, 0]))
        table = VGroup()
        for i, (name, kept, cut, base) in enumerate(rows_def):
            y = 0.6 - 0.58 * i
            bg = RoundedRectangle(width=6.6, height=0.46, corner_radius=0.12, fill_color=SUN_LT if base else PAPER2,
                                  fill_opacity=1, stroke_width=0).move_to([-1.75, y, 0])
            n = T(name, 15, INK, SEMIBOLD if base or name == "v0.3" else MEDIUM).move_to([c_name + 0.15, y, 0], aligned_edge=LEFT)
            k = T(f"{kept:.0f}%", 15, SUN_DK, SEMIBOLD).move_to([c_kept, y, 0])
            cutlab = "0" if cut < 0.05 else f"{cut:.1f}"
            u = T(cutlab, 15, SUN_DK if cut >= 0.05 else WARN, SEMIBOLD).move_to([c_cut + 0.55, y, 0])
            table.add(VGroup(bg, n, k, u))
        foot = T("Words cut = the longest clause of a sentence, before minus after · BayanSimplify models, test core items, as trained", 11, INK3)
        fit(foot, 6.4).move_to([-1.75, -2.45, 0])
        bench = card(3.0, 3.0, fill=SUN_LT, stroke=SUN).move_to([3.7, 0.1, 0])
        b_n = T(f"{F('bench_items'):,}", 44, SUN_DK, SEMIBOLD).move_to(bench.get_top() + DOWN * 0.75)
        b_l = T("items, split by document", 15, INK2).next_to(b_n, DOWN, buff=0.1)
        b_s = fit(T(f"{F('bench_dev')} dev · {F('bench_test'):,} test", 14, INK3), 2.7).next_to(b_l, DOWN, buff=0.2)
        b_t = T("BayanBench v2", 16, SUN_DK, SEMIBOLD).move_to(bench.get_bottom() + UP * 0.4)
        self.play(FadeIn(q, shift=RIGHT * 0.2), FadeIn(hdr), run_time=0.7)
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.15) for r in table], lag_ratio=0.25, run_time=1.8))
        self.play(FadeIn(foot), FadeIn(bench), FadeIn(b_n), FadeIn(b_l), FadeIn(b_s), FadeIn(b_t), run_time=0.9)
        step1 = VGroup(q, hdr, table, foot, bench, b_n, b_l, b_s, b_t)
        self.step()

        # step 2: how meaning is measured: Gemma 4 31B, seven yes/no scores
        src_c = chip("original + rewrite", fill=PAPER2, color=INK2, size=15)
        gem = VGroup(card(2.9, 0.95, fill=SUN_LT, stroke=SUN),
                     T("Gemma 4 31B", 20, SUN_DK, SEMIBOLD), T("open model · reruns anywhere", 12, INK3))
        gem[1].move_to(gem[0].get_center() + UP * 0.18)
        gem[2].move_to(gem[0].get_center() + DOWN * 0.22)
        out_c = chip("7 yes/no questions → P(yes)", fill=PAPER2, color=INK2, size=15)
        flow = VGroup(src_c, gem, out_c).arrange(RIGHT, buff=0.9).move_to([0, 1.65, 0])
        farr = VGroup(Arrow(src_c.get_right(), gem.get_left(), buff=0.1, color=SUN, stroke_width=3, max_tip_length_to_length_ratio=0.4),
                      Arrow(gem.get_right(), out_c.get_left(), buff=0.1, color=SUN, stroke_width=3, max_tip_length_to_length_ratio=0.4))

        def qcard(x, title, rows, hi=None, sub=None):
            c = card(4.7, 2.75)
            ttl = T(title, 17, SUN_DK, SEMIBOLD).move_to(c.get_top() + DOWN * 0.36)
            chips = VGroup(*[chip(r, fill=SUN if i == hi else PAPER, color=NIGHT if i == hi else INK2, size=13,
                                  weight=SEMIBOLD if i == hi else MEDIUM) for i, r in enumerate(rows)]).arrange(DOWN, buff=0.12)
            fit(chips, 4.3).move_to(c.get_center() + DOWN * 0.15)
            g = VGroup(c, ttl, chips)
            if sub:
                s_ = fit(T(sub, 11, INK3), 4.3).move_to(c.get_bottom() + UP * 0.2)
                g.add(s_)
            return g.move_to([x, -0.85, 0])

        qa = qcard(-2.6, "Meaning · 4 questions",
                   ["same meaning?  kept = yes ≥ 0.5 and every number kept", "adds a fact?", "drops a fact?", "contradicts?"], hi=0)
        qb = qcard(2.6, "Quality · 3 questions, diagnostic",
                   ["Arabic correct?", "coherent?", "easier to read?"], sub="people barely agree on these: never used to decide")
        self.play(FadeOut(step1), run_time=0.5)
        self.play(FadeIn(src_c), GrowArrow(farr[0]), FadeIn(gem), GrowArrow(farr[1]), FadeIn(out_c), run_time=1.2)
        self.play(FadeIn(qa, shift=UP * 0.12), run_time=0.8)
        self.play(FadeIn(qb, shift=UP * 0.12), run_time=0.8)
        stage_m = VGroup(src_c, gem, out_c, farr, qa, qb)
        self.step()

        # step 2: four measures, a square
        measures = [
            ("Meaning", "Does it still say the same thing?\nSame meaning, every number intact."),
            ("Simpler", "Are long clauses shorter?\nWords cut from the longest clause."),
            ("Restraint", "Does it leave alone what should\nstay? Easy text, scripture."),
            ("Copying rate", "How often is the text returned\nunchanged? A copy counts as\nperfect meaning, so we report it."),
        ]
        grid = VGroup()
        for n, expl in measures:
            c = card(4.5, 1.85)
            title = T(n, 24, SUN_DK, SEMIBOLD).move_to(c.get_top() + DOWN * 0.42)
            body = fit(T(expl, 14, INK2, line_spacing=0.95), 4.1, 1.1).move_to(c.get_center() + DOWN * 0.3)
            grid.add(VGroup(c, title, body))
        for i, g in enumerate(grid):
            g.move_to([(-1 if i % 2 == 0 else 1) * 2.5, 1.0 - 2.05 * (i // 2), 0])
        self.play(FadeOut(stage_m), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(g, scale=0.92) for g in grid], lag_ratio=0.25, run_time=1.4))
        self.hold()

        # step 3: do people agree with the scorer? The reader is the headline.
        auc = T(f"{F('judge_auc_human')}", 64, SUN, SEMIBOLD).move_to([-3.6, 0.9, 0])
        auc_l = T("scorer vs human raters (AUC)", 14, INK2).next_to(auc, DOWN, buff=0.1)
        auc_s = T(f"{F('rater_n')} raters · {F('human_tasks')} tasks", 12, INK3).next_to(auc_l, DOWN, buff=0.08)
        notes = VGroup(
            chip(f"catches {F('human_caught')} of {F('human_losses')} changed outputs", fill=PAPER2, color=INK2, size=13),
            chip(f"fails {F('human_wrongfail')} of {F('human_kept')} that people kept: stricter", fill=PAPER2, color=INK2, size=13),
            chip("raters barely agree on ease", fill=WARN_LT, color=WARN, size=13),
        ).arrange(DOWN, buff=0.12, aligned_edge=LEFT)
        fit(notes, 4.2).move_to([-5.0, -1.4, 0], aligned_edge=LEFT)

        panel = card(5.0, 3.7, fill=SUN_LT, stroke=SUN).move_to([2.4, -0.05, 0])
        r_t = fit(T(f"A reader with dyslexia\nrated {F('reader_n')} outputs", 26, SUN_DK, SEMIBOLD, line_spacing=0.95), 4.5)
        r_t.move_to(panel.get_top() + DOWN * 0.85)
        total = F("reader_easier") + F("reader_same") + F("reader_harder")
        bw = 4.3
        segs = VGroup()
        for n, col in [(F("reader_easier"), SUN), (F("reader_same"), PAPER3), (F("reader_harder"), WARN)]:
            segs.add(Rectangle(width=bw * n / total, height=0.6, fill_color=col, fill_opacity=1, stroke_width=0))
        segs.arrange(RIGHT, buff=0).move_to(panel.get_center() + DOWN * 0.35)
        labs = VGroup(*[T(f"{n} {name}", 15, INK2, MEDIUM) for n, name in [
            (F("reader_easier"), "easier"), (F("reader_same"), "same"), (F("reader_harder"), "harder")]])
        for lab, seg in zip(labs, segs):
            lab.next_to(seg, DOWN, buff=0.15)
        labs.arrange(RIGHT, buff=0.5).next_to(segs, DOWN, buff=0.2)
        r_c = T("a sample of one, not a study", 12, INK3).move_to(panel.get_bottom() + UP * 0.3)
        self.play(FadeOut(grid), run_time=0.5)
        self.play(FadeIn(panel), FadeIn(r_t), run_time=0.7)
        self.play(*[GrowFromEdge(s, LEFT) for s in segs], run_time=0.9)
        self.play(FadeIn(labs), FadeIn(r_c), run_time=0.5)
        self.play(FadeIn(auc, scale=0.9), FadeIn(auc_l), FadeIn(auc_s), run_time=0.7)
        self.play(LaggedStart(*[FadeIn(n, shift=UP * 0.1) for n in notes], lag_ratio=0.3, run_time=0.9))


# ---------------------------------------------------------------- 6. results
def _forest_row(label, est, lo, hi, scale, fmt, good, y, axis_x=1.2, half=2.6):
    """One row: label on the left, estimate and its 95% interval on a short axis (zero in the middle)."""
    col = SUN_DK if good else WARN
    lab = fit(T(label, 14, INK2), 4.3).move_to([-5.0, y, 0], aligned_edge=LEFT)
    px = lambda v: axis_x + max(-1, min(1, v / scale)) * half
    axis = Line([axis_x - half, y, 0], [axis_x + half, y, 0], stroke_color=PAPER3, stroke_width=3)
    zero = Line([axis_x, y - 0.13, 0], [axis_x, y + 0.13, 0], stroke_color=INK4, stroke_width=2)
    ci = Line([px(lo), y, 0], [px(hi), y, 0], stroke_color=col, stroke_width=6)
    dot = Dot([px(est), y, 0], radius=0.1, color=col)
    val = T(fmt(est), 14, col, SEMIBOLD).move_to([axis_x + half + 0.25, y, 0], aligned_edge=LEFT)
    return VGroup(lab, axis, zero, ci, dot, val)


class S6Results(Deck):
    NUM, KICKER, TITLE, TOTAL = 6, "05 · Results", "v0.3 is our best model", TOTAL

    def build(self):
        self.begin_beat()

        # step 1: the trade-off, and where v0.3 sits
        px0, py0, pw, ph = -2.3, -0.25, 5.2, 3.3
        x0, x1, y0, y1 = 30, 105, -0.6, 7.6
        ax = VGroup(Line([px0 - pw / 2, py0 - ph / 2, 0], [px0 + pw / 2, py0 - ph / 2, 0], stroke_color=INK4, stroke_width=2),
                    Line([px0 - pw / 2, py0 - ph / 2, 0], [px0 - pw / 2, py0 + ph / 2, 0], stroke_color=INK4, stroke_width=2))
        xl = T("meaning kept (%)  →", 12, INK3).next_to(ax[0], DOWN, buff=0.18)
        yl = T("simplification: words cut from the longest clause  →", 12, INK3).rotate(PI / 2).next_to(ax[1], LEFT, buff=0.18)
        fit(yl, 3.2)
        xy = lambda x, y: [px0 - pw / 2 + (x - x0) / (x1 - x0) * pw, py0 - ph / 2 + (y - y0) / (y1 - y0) * ph, 0]
        pts = VGroup()
        for lab, x, y, col, side, size in [
            ("Copy the input", 100.0, 0.0, INK4, UP, 12),
            ("v0.1", F("bt_m1_kept"), 0.0, INK3, UP, 12),
            ("v0.2 in the app", F("v02_app_kept"), F("v02_app_clause"), INK3, UP, 12),
            ("v0.2 (no tag)", F("t5_untag_kept"), F("t5_untag_clause"), INK3, LEFT, 11),
            ("v0.2 + tag", F("t5_tag_kept"), F("t5_tag_clause"), INK3, DOWN, 11),
            ("v0.2-Fast (no tag)", F("bart_untag_kept"), F("bart_untag_clause"), INK3, DOWN, 11),
            ("v0.2-Fast + tag", F("bart_tag_kept"), F("bart_tag_clause"), INK3, RIGHT, 11),
            ("v0.3 in the app", F("v03_kept"), F("v03_clause"), SUN_DK, RIGHT, 14),
        ]:
            best = lab.startswith("v0.3")
            d = Dot(xy(x, y), radius=0.17 if best else 0.12, color=col)
            tl = T(lab, size, SUN_DK if best else INK2, SEMIBOLD if best else MEDIUM).next_to(d, side, buff=0.12)
            pts.add(VGroup(d, tl))
        halo = Circle(radius=0.3, stroke_color=SUN, stroke_width=2, fill_opacity=0).move_to(pts[-1][0])
        src = source_badge("BayanBench v2, test core items").next_to(ax[0], DOWN, buff=0.62)
        fit(src, 6.0)
        side_note = VGroup(
            chip("the more it simplifies,\nthe less meaning it keeps, obviously", fill=SUN_LT, color=SUN_DK, size=15, weight=SEMIBOLD),
            chip(f"v0.3 keeps the most meaning ({F('v03_kept')}%)\nand still cuts {F('v03_clause')} words off\nthe longest clause", fill=SUN, color=NIGHT, size=15, weight=SEMIBOLD),
            chip("v0.3 is the app's large model,\ndecoded with four beams", fill=PAPER2, color=INK2, size=14),
        ).arrange(DOWN, buff=0.2, aligned_edge=LEFT)
        fit(side_note, 3.9).move_to([1.35, 0.1, 0], aligned_edge=LEFT)
        self.play(Create(ax), FadeIn(xl), FadeIn(yl), run_time=0.8)
        self.play(LaggedStart(*[FadeIn(p, scale=0.6) for p in pts], lag_ratio=0.18, run_time=2.0))
        self.play(Create(halo), FadeIn(src), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(n, shift=UP * 0.1) for n in side_note], lag_ratio=0.3, run_time=1.2))
        stage1 = VGroup(ax, xl, yl, pts, halo, src, side_note)
        self.step()

        # step 2: v0.3 minus v0.2 behind the same text step
        sub = T("In the app: v0.3 (four beams) minus v0.2, same text step, test core, 95% interval", 13, INK3)
        fit(sub, W - 1.6).move_to([0, 1.95, 0])
        rows = VGroup(
            _forest_row("words cut from the longest clause", F("v03_clause_diff"), 2.4, 4.4, 6, lambda v: f"+{v:.1f}", True, 1.45),
            _forest_row("hard words removed", F("v03_hard_diff"), 0.14, 0.35, 0.4, lambda v: f"+{v:.2f}", True, 0.9),
            _forest_row("reading levels lowered", F("v03_level_diff"), 0.0, 0.16, 0.3, lambda v: f"+{v:.2f}", True, 0.35),
            _forest_row("meaning kept (points): no significant difference", F("v03_kept_diff"), -7, 1, 15,
                        lambda v: f"{v:+.0f}".replace("-", "−"), True, -0.2),
        )
        chipA = chip(f"+{F('v03_easy_diff')} points more easy text left unchanged · every number kept ({F('v03_numbers')}%)",
                     fill=SUN_LT, color=SUN_DK, size=14)
        fit(chipA, W - 1.8).move_to([0, -1.05, 0])
        self.play(FadeOut(stage1), run_time=0.5)
        self.play(FadeIn(sub), run_time=0.4)
        self.play(LaggedStart(*[FadeIn(r, shift=RIGHT * 0.15) for r in rows], lag_ratio=0.3, run_time=1.6))
        self.play(FadeIn(chipA, shift=UP * 0.1), run_time=0.6)
        self.hold()

        # step 3: people agree
        head = T(f"Blind rating by the team: {F('hm_sentences')} sentences", 18, INK, SEMIBOLD).move_to([0, 1.95, 0])
        sub2 = T("outputs the system changed, rated easier to read", 13, INK3).next_to(head, DOWN, buff=0.12)
        bars = VGroup()
        for i, (name, pct, col) in enumerate([("v0.3", F("hm_v03_easier"), SUN), ("v0.2", F("hm_v02_easier"), PAPER3),
                                              ("v0.2-Fast", F("hm_fast_easier"), PAPER3)]):
            y = 0.95 - 0.62 * i
            lab = T(name, 15, INK, SEMIBOLD if i == 0 else MEDIUM).move_to([-4.3, y, 0], aligned_edge=LEFT)
            bar = Rectangle(width=6.0 * pct / 100, height=0.42, fill_color=col, fill_opacity=1, stroke_width=0)
            bar.move_to([-2.4 + bar.width / 2, y, 0])
            val = T(f"{pct}%", 15, SUN_DK if i == 0 else INK2, SEMIBOLD).next_to(bar, RIGHT, buff=0.15)
            bars.add(VGroup(lab, bar, val))
        chipD = chip(f"meaning kept in {F('hm_v03_same')}% of ratings (v0.2: {F('hm_v02_same')}%, v0.2-Fast: {F('hm_fast_same')}%) · none rated harder",
                     fill=PAPER2, color=INK2, size=14)
        chipE = chip(f"{F('hm_votes')} of {F('hm_votes')} team votes chose v0.3 over v0.2", fill=SUN_LT, color=SUN_DK, size=15, weight=SEMIBOLD)
        n_cmp = F("hm_reader_v03_v02") + F("hm_reader_v03_fast")
        chipF = chip(f"the reader with dyslexia chose v0.3 in {n_cmp} of {n_cmp} comparisons it was in · "
                     f"{F('hm_sentences')} sentences: a direction, not a size", fill=PAPER2, color=INK2, size=13)
        chips = VGroup(chipD, chipE, chipF).arrange(DOWN, buff=0.18)
        fit(chips, W - 1.8).move_to([0, -1.55, 0])
        self.play(FadeOut(VGroup(sub, rows, chipA)), run_time=0.5)
        self.play(FadeIn(head), FadeIn(sub2), run_time=0.5)
        self.play(LaggedStart(*[FadeIn(b, shift=RIGHT * 0.15) for b in bars], lag_ratio=0.3, run_time=1.4))
        self.play(LaggedStart(*[FadeIn(c, shift=UP * 0.1) for c in chips], lag_ratio=0.3, run_time=1.2))


# ---------------------------------------------------------------- 7. on a phone
class S7Phone(Deck):
    NUM, KICKER, TITLE, TOTAL = 7, "06 · On a phone", "", TOTAL

    def build(self):
        # One step. When the recording exists, pass it to `step(src=...)` and manim-slides
        # will play it as this slide's video (see the Deck.step docstring in common.py).
        head = T("What the app does", 26, INK, SEMIBOLD).move_to([0, 2.0, 0])
        body = RoundedRectangle(width=2.75, height=4.3, corner_radius=0.3, fill_color=NIGHT,
                                fill_opacity=1, stroke_color=INK4, stroke_width=2).move_to([0, -0.5, 0])
        scr = RoundedRectangle(width=2.5, height=3.9, corner_radius=0.18, fill_color=PAPER2,
                               fill_opacity=1, stroke_width=0).move_to(body)
        icon = T("▶", 44, INK3).move_to(scr)
        cap = T("recording goes here", 13, INK3).next_to(icon, DOWN, buff=0.25)
        self.play(FadeIn(head), run_time=0.5)
        self.play(FadeIn(body), FadeIn(scr), FadeIn(icon), FadeIn(cap), run_time=0.8)


# ---------------------------------------------------------------- 8. close
class S8Close(Deck):
    NUM, DARK, TOTAL = 8, True, TOTAL

    def build(self):
        self.begin_beat()
        mark = svg("bayan-mark-dark.svg", width=2.4).move_to([0, 2.0, 0])
        line = T("Simplify where you read.", 36, CREAM, SEMIBOLD).next_to(mark, DOWN, buff=0.35)
        self.play(FadeIn(mark, scale=0.9), FadeIn(line, shift=UP * 0.2), run_time=1.0)
        self.hold()

        limits = VGroup(
            chip("no reader has used Bayan; one reader rated 30 outputs", fill=NIGHT2, color=INK4, size=15),
            chip("our scorer is stricter than people", fill=NIGHT2, color=INK4, size=15),
            chip(f"the comparison with people covers {F('hm_sentences')} sentences", fill=NIGHT2, color=INK4, size=15),
        ).arrange(DOWN, buff=0.14).next_to(line, DOWN, buff=0.45)
        nxt = T("Next: a reading study with more readers.", 17, SUN, MEDIUM).next_to(limits, DOWN, buff=0.4)
        thanks = T("Thank you  ·  Team Cogni  ·  Samsung Innovation Campus", 14, INK4)
        thanks.next_to(nxt, DOWN, buff=0.3)
        self.play(LaggedStart(*[FadeIn(m, shift=UP * 0.1) for m in limits], lag_ratio=0.3, run_time=1.0))
        self.play(FadeIn(nxt), FadeIn(thanks), run_time=0.7)
