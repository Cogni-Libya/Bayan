"""Every figure that may appear on a slide, with the file or PR it comes from.

Nothing in the deck is allowed to type a number by hand. `check_numbers.py` verifies each `src`
before anything is rendered. Values here are literals deliberately: they are the checked numbers,
and their provenance travels with them.

Where a figure has an interval, the interval is in `note` so the deck can show it and the script
can speak it.

Named `facts.py`, not `numbers.py`: that name shadows the stdlib `numbers` module and numpy will
not import.
"""
from pathlib import Path

# --- where things live -------------------------------------------------------
# This file lives at Bayan-worktrees/presentation/deliverables/04_presentation/build/facts.py.
# The main repo and its .claude/worktrees are under ~/Programming/Bayan.
_here = Path(__file__).resolve()
WT = _here.parents[4]                                          # ~/Programming/Bayan-worktrees
BAYAN = WT.parent / "Bayan"                                    # ~/Programming/Bayan
FINAL_REPORT_TEX = WT / "final-report/deliverables/03_final_report/latex"
BENCH_REPORT = WT / "benchmark-report/docs/benchmark_report"
CORPUS_V1 = BAYAN / ".claude/worktrees/corpus-v1-gemma-qwen"
COMPARE_REPORT = BAYAN / "data/processed/meaning_reward/compare/report"


# Figures from the newest report are verified against its text in git, not against a worktree.
REPORT_REF = "ba4e299"                                  # Marwan's combined report (PR #70; was origin/docs/final-report-draft)
REPORT_DIR = "deliverables/03_final_report/latex"


def G(file, needle):
    """Provenance string `check_numbers.py` verifies: `needle` must appear in REPORT_REF's `file`
    (whitespace collapsed)."""
    return f"git:{REPORT_REF}:{REPORT_DIR}/{file}::{needle}"


def GR(path, needle):
    """Like G, for a file at the repo root (README.md) on the report branch."""
    return f"git:{REPORT_REF}:{path}::{needle}"


BENCH_PDF = "khengari77/benchmark-report:docs/benchmark_report/bayan_benchmark_report.pdf"


def P(row):
    """Provenance: a row of Table 3 (test split, core items) of the benchmark report PDF, verified with pdftotext."""
    return f"pdf:{BENCH_PDF}::{row}"


PEER = "peer: bayan-f7 session, 5 Oct 2026 (copies.py over bayanbench-submissions report/* and meaning/*.jsonl); not re-run here"

# A figure is (value, src, note). `src` is either a path relative to something in PATHS, or a
# literal like "PR #58" meaning the pull request body. `check_numbers.py` resolves both.
FIG = {
    # ---- product, problem -------------------------------------------------
    "dyslexia_pct": (
        11,
        G("main.tex", r"estimated 11\% of Arab primary-school children"),
        "11% of Arab primary-school children; Aldakhil 2024, Res Dev Disabil 152:104812",
    ),
    "latency_s_per_sentence": (
        0.17,
        "benchmark-report facts.json bundles/device",
        "model 3 app int8 bundle, i7-12700 AVX-VNNI, 4 threads",
    ),
    "bundle_mb": (
        471,
        "benchmark-report facts.json bundles",
        "model 3 app int8 bundle: encoder 170 + decoder 285 + tokenizer 15 MB. NOT 250 MB.",
    ),
    "bundle_mb_prev": (
        222,
        "benchmark-report compare/report report.md (AraBART int8)",
        "model 2 AraBART int8 bundle; kept only for Q&A, never on a slide",
    ),

    # ---- corpus v1 pipeline (beat 2) --------------------------------------
    "route_easy": (16599, "corpus-v1 run_retry.log:5", "non-test BAREC routed easy"),
    "route_hard": (23221, "corpus-v1 run_retry.log:5", "non-test BAREC routed hard"),
    "route_protected": (2274, "corpus-v1 run_retry.log:5", "non-test BAREC routed protected"),
    "route_short": (18488, "corpus-v1 run_retry.log:5", "non-test BAREC routed short"),
    "gen_responses": (23205, "corpus-v1 synthetic_data_card_v1.md:77", "usable Gemma 4 31B responses"),
    "accepted_tier_a": (10693, "corpus-v1 assemble.log:1", "equivalence >= 0.85 and lead >= 2.0"),
    "tier_b_not_shipped": (1220, "corpus-v1 synthetic_data_card_v1.md:80", "tier B (0.75-0.85) was not shipped"),
    "structure_rejects": (9, "corpus-v1 run_retry.log:42", "sources with no eligible candidate"),
    "protected_pulled": (315, "corpus-v1 assemble.log:2", "protected classifier pull-out"),
    "leak_dropped_texts": (35, "corpus-v1 assemble.log:3", "BAREC-test leak texts dropped"),
    "leak_dropped_rows": (52, "corpus-v1 assemble.log:3", "BAREC-test leak rows dropped"),
    "mix_generated": (10382, "corpus-v1 assemble.log:4", "generated pairs in the mix"),
    "mix_identity": (2483, "corpus-v1 assemble.log:4", "easy identity pairs"),
    "mix_protected": (1375, "corpus-v1 assemble.log:4", "protected identity pairs"),
    "mix_short": (747, "corpus-v1 assemble.log:4", "short identity pairs"),
    "corpus_rows": (14975, "corpus-v1 assemble.log + synthetic_data_card_v1.md:75", "corpus v1 total"),
    "split_train": (11935, "corpus-v1 assemble.log", "grouped split, train"),
    "split_dev": (1504, "corpus-v1 assemble.log", "grouped split, dev"),
    "split_test": (1536, "corpus-v1 assemble.log", "grouped split, test"),
    "check_violations": (0, "corpus-v1 check_corpus.log", "rule violations in corpus v1"),
    "leak_matches": (0, "corpus-v1 leakage_train.log", "5+ word matches vs BAREC test"),
    "audit_n": (1039, "corpus-v1 synthetic_data_card_v1.md:150", "pairs in the blind audit"),
    "audit_same": (84.9, "corpus-v1 synthetic_data_card_v1.md:150", "audit: same meaning"),
    "audit_minor": (13.4, "corpus-v1 synthetic_data_card_v1.md:150", "audit: minor change"),
    "audit_changed": (1.7, "corpus-v1 synthetic_data_card_v1.md:150", "audit: meaning changed"),
    "meaning_gate": (0.85, "corpus-v1 synthetic_data_card_v1.md:80", "Qwen gate that shipped (tier A). 0.75 is only the logged floor."),

    # ---- corpus v0 defects (why the gates exist) --------------------------
    "v0_tashkeel": (56.5, G("main.tex", r"tashkeel in 56.5\% of rows"), "v0 rows containing tashkeel"),
    "v0_completed": (63.4, G("main.tex", r"63.4\% of cut-off sources"), "v0 cut-off sources the generator completed"),
    "v0_short_rewritten": (11.1, G("main.tex", r"11.1\% of short"), "v0 short sources rewritten"),
    "v0_levels": (42.9, G("main.tex", r"42.9\% of pairs at"), "v0 pairs at least 2 CAMeL levels easier"),

    # ---- model 2 findings (beat 3) ---------------------------------------
    # Q&A only. The 22,733 mix is the Baseet-era set; the user asked us to drop it from the
    # story, so it must not reach a slide. `check_numbers.py` enforces that.
    "m2_pairs": (22733, "issue #52 holds-up list", "model 2 training pairs; Q&A only, never on a slide"),
    "m2_meaning_tagged": (0.59, "issue #52 A3 / #48", "AraT5v2 tagged, meaning kept, Gemma 4 31B"),
    "m2_meaning_arabart": (0.40, "issue #52 A3 / #48", "AraBART tagged, meaning kept"),
    "m2_meaning_untagged": (0.68, "issue #52 C4", "AraT5v2 untagged: the tag costs meaning"),
    "m2_int8_changed": (74, "issue #52 A5", "share of AraT5 outputs int8 changed (62-74%)"),

    # ---- BayanBench v2.0 frozen rule (beat 4) ----------------------------
    "judge_auc": (0.85, "PR #55 body", "Gemma 4 31B vs human majority 'same'; [0.79, 0.90]"),
    "rater_tasks": (290, "PR #55 body", "3 Oct human rating round"),
    "rater_n": (6, "PR #55 body", "raters in that round"),
    "alpha_meaning": (0.51, G("human.tex", r"hAlphaMeaning"), "Krippendorff alpha, meaning"),
    "alpha_arabic": (0.17, G("human.tex", r"hAlphaMeaning"), "Krippendorff alpha, Arabic"),
    "alpha_ease": (0.19, G("human.tex", r"hAlphaMeaning"), "Krippendorff alpha, ease"),
    "v1_measure_auc": (0.50, "issue #48 body", "retention and the 15-word rule vs human labels"),
    "systems_scored": (35, "PR #58 body", "systems on BayanBench v2.0"),
    "scorecards": (70, "PR #58 body", "35 systems x dev/test"),

    # ---- ship gate: model 3 + net vs today's app (beats 3-4) -------------
    "ship_p_same": (0.83, "PR #58 body", "test core, model 3 app int8 + beam 4 + net"),
    "app_p_same": (0.79, "PR #58 body", "test core, today's app"),
    "p_same_diff": (0.04, "PR #58 body", "paired, [-0.00, +0.08]"),
    "ship_numbers_kept": (100, "PR #58 body", "test core"),
    "app_numbers_kept": (84, "PR #58 body", "test core"),
    "ship_easy_unchanged": (74, "PR #58 body", "test core, easy text left unchanged"),
    "app_easy_unchanged": (48, "PR #58 body", "test core"),
    "clause_gain": (3.5, "PR #58 body", "words shorter than the app, [2.5, 4.5]"),
    "ship_unchanged_rate": (47, "PR #58 body", "caveat: share of items left unchanged; app 19%"),
    "ship_p_same_changed": (0.67, "PR #58 body", "caveat: P(same) on the outputs it does change"),
    "app_p_same_changed": (0.74, "PR #58 body", "caveat: the app's P(same) on changed outputs"),
    "dev_p_same_diff": (0.08, "PR #56 body", "dev core gate, [-0.00, +0.17]"),
    "dev_clause_gain": (4.3, "PR #56 body", "dev core gate, [3.0, 5.7]"),
    "dev_level_gain": (0.27, "PR #56 body", "dev core gate, [0.15, 0.42]"),


    # ---- data: what existed and what we tried before v1 ------------------
    "samer_identity_lo": (42, G("main.tex", r"42--49\% of pairs are identical"), "SAMER pairs where target equals source (train 42.1%, test 48.8%)"),
    "samer_identity_hi": (49, G("main.tex", r"42--49\% of pairs are identical"), ""),
    "samer_ratio": (1.00, G("main.tex", r"median length ratio is exactly 1.00"), "SAMER: editors swapped words, kept structure"),
    "external_kept": (6888, G("main.tex", r"keeps 6,888 pairs"), "external LLM-written pairs that passed the meaning filter"),
    "v0_validator_added": (34, G("main.tex", r"accepted 34\% of added sentences"), "planted added sentences the v0 validator accepted at 0.7"),
    # ======================= v2 deck (4 minutes) ===========================
    # ---- problem ---------------------------------------------------------
    "dyslexia_studies": (18, G("main.tex", r"pooled across 18 studies"), "studies in the pooled estimate"),
    "dyslexia_n": (30243, G("main.tex", r"$N$ = 30,243"), "children in those studies"),
    # ---- the app ---------------------------------------------------------
    "guards_numbers_before": (72, G("main.tex", r"raise numbers kept from 72\% to 100\%"), "dev core items, before the guards"),
    "guards_numbers_after": (100, G("main.tex", r"raise numbers kept from 72\% to 100\%"), "dev core items, with the guards"),
    "guards_meaning_gain": (3.5, G("main.tex", r"raise meaning kept by about 3.5 points"), "points, dev core items"),
    "phone_bart_mb": (222, G("main.tex", r"\textbf{222\,MB} (212\,MiB)"), "AraBART int8, the default"),
    "phone_t5_mb": (471, G("main.tex", r"471\,MB (449\,MiB)"), "AraT5v2 int8 bundles (model 2 large, model 3), optional"),
    "phone_bart_ms": ("82-172", G("main.tex", r"82--172\,ms"), "first word, first sentence, Xiaomi Mi 11X, six cold starts"),
    "phone_t5_ms": ("177-318", G("main.tex", r"177--318\,ms"), "first word, first sentence, AraT5v2 int8"),
    "beam_s": (1.19, G("main.tex", r"it takes 1.19\,s per sentence"), "model 3, four beams, phone median"),
    "greedy_s": (0.41, G("main.tex", r"against 0.41\,s when the same bundle decodes greedily"), "model 3, greedy, phone median"),
    # ---- model 1 ---------------------------------------------------------
    "m1_copy_pct": (65.3, G("results.tex", r"\newcommand{\greedycopy}{65.3}"), "share of test rows model 1 returns unchanged"),
    "m1_editor_copy_pct": (48.8, G("results.tex", r"\newcommand{\humancopy}{48.8}"), "share the editors left unchanged"),
    # ---- model 2 on BayanBench, test core, as benchmarked (F1) -----------
    "t5_tag_kept": (59.5, G("bench_v2.tex", r"\newcommand{\bvHTfiveKept}{59.5}"), "AraT5v2 [S2], meaning kept %, test core"),
    "t5_tag_clause": (6.3, G("bench_v2.tex", r"\newcommand{\bvHTfiveClause}{6.3}"), "words cut from the longest clause"),
    "bart_tag_kept": (40.1, G("bench_v2.tex", r"\newcommand{\bvHBartKept}{40.1}"), "AraBART [S2]"),
    "bart_tag_clause": (6.7, G("bench_v2.tex", r"\newcommand{\bvHBartClause}{6.7}"), ""),
    "t5_untag_kept": (68.3, G("bench_v2.tex", r"\newcommand{\bvHTfiveNKept}{68.3}"), "AraT5v2 no tag"),
    "t5_untag_clause": (4.5, G("bench_v2.tex", r"\newcommand{\bvHTfiveNClause}{4.5}"), ""),
    "bart_untag_kept": (51.4, G("bench_v2.tex", r"\newcommand{\bvHBartNKept}{51.4}"), "AraBART no tag"),
    "bart_untag_clause": (4.9, G("bench_v2.tex", r"\newcommand{\bvHBartNClause}{4.9}"), ""),
    "app_t5_kept": (78.6, G("bench_v2.tex", r"\newcommand{\bvHAppTfiveKept}{78.6}"), "the shipped AraT5v2 int8 bundle (September text step)"),
    "app_t5_clause": (1.9, G("bench_v2.tex", r"\newcommand{\bvHAppTfiveClause}{1.9}"), ""),
    "easy_unchanged_min": (11.7, G("bench_v2.tex", r"\newcommand{\bvHminC}{11.7}"), "easy text left unchanged, lowest system"),
    "easy_unchanged_max": (48.1, G("bench_v2.tex", r"\newcommand{\bvHmaxC}{48.1}"), "easy text left unchanged, highest system"),
    # ---- BayanBench and the people check ---------------------------------
    "bench_items": (1981, G("main.tex", r"The 1,981 items form four sets"), ""),
    "bench_dev": (731, G("main.tex", r"731 dev items from 129 documents"), ""),
    "bench_test": (1250, G("main.tex", r"1,250 test items from 197"), ""),
    "human_tasks": (290, G("human.tex", r"\newcommand{\hTasks}{290}"), "rating tasks, six raters"),
    "judge_auc_human": (0.85, G("human.tex", r"\newcommand{\hAucSame}{0.85}"), "scorer vs human majority 'same'; interval 0.78-0.91"),
    "human_caught": (42, G("human.tex", r"\newcommand{\hCaught}{42}"), "of the changed outputs the raters found"),
    "human_losses": (51, G("human.tex", r"\newcommand{\hLosses}{51}"), ""),
    "human_wrongfail": (53, G("human.tex", r"\newcommand{\hWrongFail}{53}"), "the scorer failed these outputs that raters kept"),
    "human_kept": (194, G("human.tex", r"\newcommand{\hKept}{194}"), ""),
    "reader_n": (30, G("human.tex", r"\newcommand{\rN}{30}"), "outputs rated by the reader with dyslexia"),
    "reader_easier": (17, G("human.tex", r"\newcommand{\rEasier}{17}"), ""),
    "reader_same": (9, G("human.tex", r"\newcommand{\rSame}{9}"), ""),
    "reader_harder": (4, G("human.tex", r"\newcommand{\rHarder}{4}"), ""),
    # ---- raw models on BayanBench, test core, benchmark report Table 3 ------
    "bt_m1_kept": (76, P("Model 1 0.76 76 1 -0.0 0.09 0.30"), "model 1, meaning kept %"),
    "bt_m1_clause": (0.0, P("Model 1 0.76 76 1 -0.0 0.09 0.30"), "model 1, words cut from the longest clause (-0.0)"),
    "bt_m3_kept": (69, P("Model 3 greedy 0.69 69 25 9.5 0.49 0.77"), "model 3, float, greedy, no net"),
    "bt_m3_clause": (9.5, P("Model 3 greedy 0.69 69 25 9.5 0.49 0.77"), "words cut from the longest clause"),
    # ---- BayanSimplify v0.3 (model 3) after the #68 correction, 5 Oct ------
    "v03_kept": (82, GR("README.md", "| **app, BayanSimplify-v0.3 int8, four beams** | **82%** | **5.2** |"), "meaning kept %, test core, int8, 4 beams + net, app text step"),
    "v03_clause": (5.2, GR("README.md", "| **app, BayanSimplify-v0.3 int8, four beams** | **82%** | **5.2** |"), "words cut from the longest clause"),
    "v02_app_kept": (78.6, GR("README.md", "| app, v0.2 int8 / v0.2-Fast int8 (September text step) | 78.6% / 50.5% | 1.9 / 4.8 |"), "v0.2 int8, September text step"),
    "v02_app_clause": (1.9, GR("README.md", "| app, v0.2 int8 / v0.2-Fast int8 (September text step) | 78.6% / 50.5% | 1.9 / 4.8 |"), ""),
    "v03_kept_diff": (-3, G("model3.tex", r"\newcommand{\mBeamTKeptDiff}{\textminus 3}"), "points vs v0.2 behind the same text step, [-7, +1]: not significant (659 of 659 items)"),
    "v03_clause_diff": (3.4, G("model3.tex", r"\newcommand{\mBeamTClauseDiff}{+3.4}"), "words, [+2.4, +4.4]"),
    "v03_hard_diff": (0.24, G("model3.tex", r"\newcommand{\mBeamTHardDiff}{+0.24}"), "hard words, [+0.14, +0.35]"),
    "v03_level_diff": (0.08, G("model3.tex", r"\newcommand{\mBeamTLevelDiff}{+0.08}"), "levels, [+0.00, +0.16]"),
    "v03_easy_diff": (18, G("model3.tex", r"\newcommand{\mBeamTEasyDiff}{+18}"), "points more easy text left unchanged"),
    "v03_numbers": (100, G("model3.tex", r"\newcommand{\mBeamTNumbers}{100}"), "numbers kept"),
    "hm_sentences": (18, G("main.tex", r"It used 18 BayanBench"), "sentences in the v0.3 rating round, blind, team raters"),
    "hm_v03_easier": (86, G("human_m3.tex", r"\newcommand{\hmThreeChEasier}{86}"), "% of changed outputs rated easier, v0.3"),
    "hm_v02_easier": (60, G("human_m3.tex", r"\newcommand{\hmTwoChEasier}{60}"), "v0.2"),
    "hm_fast_easier": (45, G("human_m3.tex", r"\newcommand{\hmBartChEasier}{45}"), "v0.2-Fast"),
    "hm_v03_same": (96, G("human_m3.tex", r"\newcommand{\hmThreeSame}{96}"), "% of ratings: meaning kept, v0.3"),
    "hm_v02_same": (96, G("human_m3.tex", r"\newcommand{\hmTwoSame}{96}"), "v0.2"),
    "hm_fast_same": (92, G("human_m3.tex", r"\newcommand{\hmBartSame}{92}"), "v0.2-Fast"),
    # ---- the reader with dyslexia, v0.3 round (24 tasks, 6 outputs per model, 2 comparisons per pair) ----
    "hm_reader_tasks": (24, G("human_m3.tex", r"\newcommand{\hmReaderTotal}{24}"), "tasks rated by the reader in the v0.3 round"),
    "hm_reader_v03_v02": (2, G("human_m3.tex", r"\newcommand{\hmPThreeTwoRFirst}{2}"), "comparisons v0.3 vs v0.2 where the reader chose v0.3, of 2"),
    "hm_reader_v03_fast": (2, G("human_m3.tex", r"\newcommand{\hmPThreeBartRFirst}{2}"), "comparisons v0.3 vs v0.2-Fast where the reader chose v0.3, of 2"),
    "hm_reader_v03_easier": (4, G("human_m3.tex", r"\newcommand{\hmThreeREasier}{4}"), "of 6 single v0.3 outputs found easier, none harder"),
    "hm_reader_v02_easier": (2, G("human_m3.tex", r"\newcommand{\hmTwoREasier}{2}"), "of 6 for v0.2"),
    "hm_reader_fast_easier": (5, G("human_m3.tex", r"\newcommand{\hmBartREasier}{5}"), "of 6 for v0.2-Fast"),
    "hm_votes": (8, G("human_m3.tex", r"\newcommand{\hmPThreeTwoFirst}{8}"), "team votes v0.3 over v0.2, of 8"),
    # ---- model 3 with 4 beams vs the current large model (peer session) ----
    "unchanged_m3_beam": (46.1, PEER, "% of test core items unchanged, model 3 int8 4 beams (659 items)"),
    "unchanged_m3_greedy": (44.8, PEER, "model 3 int8 greedy"),
    "unchanged_large": (32.3, PEER, "the current large model through the current text step"),
    "psame_m3_beam": (0.686, PEER, "mean P(same) on outputs changed in both systems, test, n=278"),
    "psame_large": (0.783, PEER, "same items, the current large model"),
    "psame_diff": (-0.097, PEER, "paired, document bootstrap 95% CI [-0.159, -0.034]"),

    # ---- the old SARI hook, retired. Kept so check_numbers can assert it
    # is never referenced by the deck. ------------------------------------
    "retired_sari_copy": (77.5, "retired", "do not put on a slide; SAMER SARI protocols disagree"),
}

# The meaning-vs-simplicity scatter, from the benchmark report. x = meaning kept, y = words
# shortened on the longest clause. Test core. Only what the deck needs plotted.
SCATTER = [
    # (label, meaning kept %, longest-clause words shorter, mark)
    ("copy", 100.0, 0.0, "baseline"),
    ("app-arat5 (today)", 78.4, 1.6, "app"),
    ("model2-arat5-notag", 77.8, 3.6, "model2"),
    ("model2-arat5", 62.5, 5.7, "model2"),
    ("app-arabart", 54.7, 4.0, "app"),
    ("model2-arabart-notag", 55.6, 3.6, "model2"),
    ("model2-arabart", 41.9, 6.0, "model2"),
    ("model 3 + net", 82.0, 5.2, "ship"),
]
SCATTER_SRC = "PR #58 body + benchmark-report docs/benchmark_report (meaning-vs-simplicity plot)"
SCATTER_NOTE = "test core, paired vs today's app; meaning kept = P(same) >= 0.5 and every number kept"

# Source paths that check_numbers.py knows how to resolve. Values are absolute paths.
PATHS = {
    "final-report": FINAL_REPORT_TEX / "main.tex",
    "figures.tex": FINAL_REPORT_TEX / "figures.tex",
    "benchmark-report": BENCH_REPORT / "report.tex",
    "facts.json": BENCH_REPORT / "facts.json",
    "corpus-v1": CORPUS_V1 / "data/processed/corpus_v1" / "assemble.log",
    "corpus-v1 check": CORPUS_V1 / "data/processed/corpus_v1" / "check_corpus.log",
    "corpus-v1 card": CORPUS_V1 / "docs" / "synthetic_data_card_v1.md",
    "corpus-v1 run_retry": CORPUS_V1 / "data/processed/v1_final" / "run_retry.log",
    "corpus-v1 leakage": CORPUS_V1 / "data/processed/corpus_v1" / "leakage_train.log",
    "compare/report": COMPARE_REPORT / "report.md",
}
