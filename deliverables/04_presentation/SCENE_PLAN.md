# Bayan pitch: scene plan (v2)

Status 5 Oct 2026. Sources read: issue #52, `docs/final-report-draft` @ `6c5c181` (Marwan's combined report, the newest), `khengari77/benchmark-report` @ `565123a` (35-system benchmark report), issue #50.
Nothing here is rendered yet. This replaces the scene list in `script_data.py` once agreed.
**SUPERSEDED on model 3 (5 Oct, issue #68): Marwan withdrew the “model 3 keeps less meaning” claim. The deck now uses the BayanSimplify names (v0.1, v0.2, v0.2-Fast, v0.3) and presents v0.3 (four beams) as our best model. Section 0a below is historical; the built scenes and `script_data.py` are the source of truth.**

## 0. What changed since the deck was written

The deck still tells the 29 Sep story. The report moved on. These are the facts that break the current script:

| # | Current deck says | Report now says | Fix |
|---|---|---|---|
| 1 | Beat 4/5: model 3 + safety net "sits at the good corner"; easy text unchanged 74% vs 48% | The grounded benchmark report (#57, 35 systems, run on our side) supports model 3: against the app it was benchmarked against, clause 5.4 vs 1.9 words, numbers 100% vs 84%, easy text unchanged 74% vs 48%, P(same) 0.83 vs 0.79. **Marwan's review on #58 disputes the ship decision**: against the *current* app text step, model 3 int8 greedy keeps meaning less on test (−8.1 [−13, −3]; dev −2.3). Provenance of that figure was asked on #58 and is unanswered; it also stays partly unscored (#65: beam-4 and 197 app test pairs). | Deck states what is grounded and labels it (see 0a). |
| 2 | Script: "AraBART's 222 MB is model 2, not what ships" | AraBART int8 (222 MB) **is the default**; AraT5v2 bundles (471 MB) are optional downloads. | Say "222 MB default, 471 MB optional". |
| 3 | "Don't say it adds diacritics" | Libtashkeel is in the app as a setting, **off by default**, untested with readers. | May mention as an option, never as a benefit. |
| 4 | "No reader has used it" only | One reader with dyslexia rated 30 outputs for ease (17 easier, 9 same, 4 harder). Still no reader has *used the app* (O4 "started"). | Say both. |
| 5 | Human round absent | Six raters, 290 tasks, scorer AUC 0.85. | New scene 6. |
| 6 | App internals absent | Guards, scripture never sent to the model, tashkeel and beam settings, read-aloud, phone timings. | New scene 3. |
| 7 | "Strength tag" implied as a feature | The app sends **no** tag: untagged keeps meaning better (68.3% vs 59.5% AraT5, test). | Never present the tag as a reader control. |

### 0a. How the deck treats model 3 (updated 5 Oct, numbers from the peer session `bayan-f7`, who has HF access)

Counted from the output files and the 31B scores, "core" = core items minus track F (659 test, 320 dev), unchanged = identical to the source after `norm()`:

| System | Unchanged, test | Unchanged, dev |
|---|---|---|
| Current large model (model 2 AraT5v2, current text step) | 32.3% | 30.6% |
| Model 3 int8 greedy | 44.8% | 41.6% |
| Model 3 int8, 4 beams | 46.1% | 43.4% |
| September baseline app | 18.8% | 19.7% |

**Does model 2 win on meaning by copying? No, the reverse.** Model 3 copies more (about 13 points on test), and a copy counts as perfect meaning, so copying flatters model 3.

Meaning on changed outputs only (copies excluded), items changed and scored in both, document-bootstrap 95% CI, model 3 with 4 beams against the current large model:
- **Test (n = 278):** 0.686 vs 0.783, paired **−0.097 [−0.159, −0.034]**.
- **Dev (n = 142):** 0.774 vs 0.822, paired −0.048 [−0.131, +0.030] (interval includes zero).

So when model 3 rewrites, it keeps less meaning, significantly on test. This agrees in direction with Marwan's −8.1 and with the benchmark report's 0.67 vs 0.74. My earlier 0.66 vs 0.78 (unmatched pending pairs) is superseded. The "47%" in the benchmark report is closest to model 3 beams (46.1% test); the "59%" I derived is wrong and is dropped.

**Deck stance (4 minutes):** model 3 is the strongest *simplifier* (clause cut, easy text left alone, protected text intact, every number kept) and it costs meaning: on what it rewrites it keeps less than the shipped large model, and beam 4 narrows but does not close that. Never "best overall", "default", or "beats the current app on meaning". Label comparisons "shipped large model", not "today's app" (the benchmark report's baseline is the September step, 18.8% unchanged). Backup B9 holds the dispute.

Provenance still open: the model 3 greedy file used for "system 2" was assumed to be the gate's file (`*_model3-int8-app.jsonl`); not checked against #58/#59.

### Conflicts between the sources: resolve before a number goes on a slide

1. **Meaning gate for corpus v1.** Report 2.1 says Qwen threshold **0.75**. The data card and our `facts.py` say the shipped gate is **0.85** (tier A 10,693 rows; tier B 0.75–0.85, 1,220, not shipped). Deck uses 0.85. Tell Marwan the report text is probably wrong.
2. **Krippendorff α for meaning.** Final report: **0.51**. Benchmark report: 0.30 / 0.38 / 0.32 (nominal / ordinal / binary). Do not put α on a slide until Marwan reconciles; the AUC (0.85) agrees in both.
3. **Corpus v1 mix** parts (10,382 + 2,483 + 1,375 + 747) sum to 14,987, not 14,975. Show only the 14,975.
4. **Benchmark report recommends shipping model 3 (beam 4 + net); the final report decides otherwise.** Unresolved (#58). The deck uses the benchmark report's measured numbers with the label and caveat in 0a.
5. **Time: 4:00** (confirmed), including clicks and the video. Backup scenes sit outside the clock.
6. `facts.py` points at `final-report/` and `benchmark-report/` worktrees at their older commits. Re-point at `docs/final-report-draft` @ `6c5c181` and re-run `check_numbers.py` before rendering.

## 1. Story

One sentence: **Bayan simplifies Arabic where you read, on the phone; most of our work was learning how to tell whether it worked, and the honest answer is a trade-off.**

Arc: problem → what the app does → data → models → how we measure → do the measures hold up → results (incl. the decision) → phone → close with limits.
The Manim "beat" model stays: each scene is one beat, 2–4 click steps, plays through, holds.

## 2. Run sheet (target 4:00, including clicks and the video)

| # | Scene | New or changed | Steps | Time | Words (≈130 wpm) | Clock |
|---|---|---|---|---|---|---|
| 1 | Cover | tweak: team strip | 1 | 0:08 | 18 | 0:08 |
| 2 | Problem and evidence | changed | 2 | 0:25 | 55 | 0:33 |
| 3 | Data | changed | 3 | 0:35 | 78 | 1:08 |
| 4 | Models | changed | 3 | 0:35 | 78 | 1:43 |
| 5 | Measuring it, and the people check | **new (merges old 5 + humans)** | 3 | 0:45 | 100 | 2:28 |
| 6 | Results | **new** | 3 | 0:45 | 100 | 3:13 |
| 7 | On a phone (app + video) | changed | 1 | 0:30 | video, 25 words | 3:43 |
| 8 | Close and limits | changed | 2 | 0:17 | 36 | 4:00 |

About 490 words, 18 steps. The standalone "app" scene of the 5-minute version is gone: its guards strip moves into scene 7 and into backup B10. Speakers: split after scene 4 / 5; names not assigned.

## 3. Scenes in detail

Frame 1444×1000, safe area x ±5.0, y 2.3 to −3.0. Reuse `fit()`, `scatter()`, `audit()`. Every number below is a `facts.py` entry with a source.

### Scene 1: Cover (unchanged, 0:08)
- Logo draws, title **Bayan تبسيط**, subtitle "On-device Arabic text simplification, and how we measured it" (the report's title).
- New: six names in a row (Marwan Elamami, Abdulrahman Khengari, Ahmed Alaeb, Sanad Ali, Mohammed Thabet, Abdul Majid Mraied), team "Cogni".
- Say: "This is Bayan: simplify hard Arabic where you read, on the phone. I'll show how we built it, and how we checked it."

### Scene 2: Problem and evidence (0:25)
1. **11%** counts up with the label "of Arab primary-school children have developmental dyslexia", badge `18 studies, N = 30,243`; then **كتب** splits into kataba / kutiba / kutub (drop the glosses). 
2. **What helps, and our scope.** Left: "Shorter clauses: read faster, understood better, most by the weakest readers" (Javourey-Bonnet 2022). Right: **we reduce reading load (long clauses, hard words) and read aloud. Not decoding. No claim yet that it helps readers with dyslexia.**
- Source line: `Aldakhil 2024; Javourey-Bonnet 2022; report 1.1`.

### Scene 3: Data, how we got to corpus v1 (0:45, 4 steps; built)
1. **What existed.** SAMER (novels; 42–49% of pairs unchanged; length ratio 1.00, swaps words, never splits) and an external LLM-written corpus (many targets are summaries; a meaning filter kept 6,888 pairs). The external corpus is not named on the slide.
2. **Our first attempt, corpus v0.** DeepSeek, 5 candidates per source → LLM equivalence validator → CAMeL readability gate. The audit found tashkeel in 56.5% of rows, 63.4% of cut-off sources completed, 11.1% of short sources rewritten, only 42.9% two levels easier; the validator accepted 34% of planted added sentences; nothing was trained on v0.
3. **Corpus v1 pipeline** as two lanes (BAREC → strip tashkeel → route → Gemma 4 31B → code, readability, meaning gates). Meaning-gate number left off (0.75 vs 0.85 conflict).
4. **14,975 rows**, 0 violations, 0 leakage, blind audit of 1,039: 1.7% meaning changed.

### Scene 4: Models (0:35): three lanes, as now, with the new content
1. **Model 1** (AraT5v2 on SAMER): "copy scores 77.50 SARI; model 75.88". Zoom: on the 1,678 rows a human changed it **wins 61.83 vs 56.06**. Found: copies 65% of rows (editors 49%), changes one word, length ratio 1.00. Example: عزلة → استعباد ("isolation" → "enslavement").
2. **Model 2** (+ everyday text with a meaning filter, keep unchanged pairs, strength tags; 22,733 pairs; AraT5v2 368M and AraBART 139M). Found: simplifies more but **tag costs meaning**; the app sends no tag.
3. **Model 3** (AraT5v2 on corpus v1) + the code safety net from scene 3. Dropped branches fade: *student DPO*, *minimum-risk training*, *fluency retrain* ("better proxies, worse on the 31B scorer").
- Say: "SARI said model 1 was worse than copying. It was not, and it was not good either. That is why we built our own yardstick."

### Scene 5: Measuring it, and the people check (0:45)
1. **Copy trap.** "Copy the input: 100% meaning, 0 simplification." Then the BayanBench card: 1,981 items split by document (731 dev, 1,250 test), four item sets, never averaged.
2. **Three kinds of measure** (columns): *Meaning* P(same) from Gemma 4 31B, kept = P ≥ 0.5 **and** every number kept · *Simpler* words cut from the longest clause, reading levels, hard words · *Restraint* easy text unchanged, protected text intact, cut-offs not completed. Footer: "scored separately, never one number; open scorer anyone can rerun, ~$0.12 per 2,700 pairs".
3. **Do people agree with the scorer?** Six raters, 290 tasks. Mini ROC or bar: **AUC 0.85 [0.78, 0.91]**; catches 42 of 51 changed outputs, all 11 major ones; but fails 53 of the 194 people kept: "stricter than people, so 'meaning kept' is conservative". 
4. **What we dropped.** Strike-through chips: first pass/fail clause and retention rules, full-stop ban, word lexicons, ease and Arabic judged by machine (raters agree only α 0.19 and 0.17). "We kept only what tracks people." The reader with dyslexia: 30 outputs, **17 easier, 9 same, 4 harder**.
- Do not show the meaning α (conflict 2). Do not say "validated" about ease or Arabic.
- Backup B2: meaning judge (95.5% of planted errors, ~30× faster than the 31B).

### Scene 6: Results (0:45), the scene the deck lacks
All numbers test split, core items, from the benchmark report (#57) and report 3.2 (`bvH*`). Comparison label: "shipped large model, as benchmarked 4 Oct".
1. **Trade-off scatter** (use `scatter()`): x meaning kept %, y words cut from the longest clause. Points: copy (100, 0); shipped large model int8 (78.6, 1.9); model 2 untagged (68.3, 4.5); model 2 tagged (59.5, 6.3); AraBART tagged (40.1, 6.7). Line: "the more it simplifies, the less meaning it keeps." Raw restraint is weak: easy text unchanged only 11.7–48.1%, protected text intact 4.4–47.8%, so the app moves that into code.
2. **Model 3 enters** (AraT5v2 on corpus v1, app int8; scatter point with a halo): clause **5.4 vs 1.9** words, numbers kept **100% vs 84%**, easy text unchanged **74% vs 48%**, protected text intact (benchmark report, test; baseline labelled "shipped large model, as benchmarked 4 Oct"). Chip: "simplifies the most".
3. **What it costs.** Meaning on rewritten outputs only, test: model 3 (4 beams) **0.69 vs 0.78**, paired **−0.10 [−0.16, −0.03]**. Footer: "it also copies more: 46% of items unchanged vs 32% (a copy counts as perfect meaning)". Chip: "beam 4 = the 'more faithful, slower' setting: narrows the gap, does not close it".
- Say: "Model three simplifies the most, keeps every number and leaves easy text alone. The price is meaning: when it rewrites, it keeps less of it than the model we ship. So it is an option, with a slower, more faithful setting."
- Do not say "best overall" or "default". Backup B9 holds the dispute.

### Scene 7: On a phone, and what the app does (0:30, mostly video)
1. Recorded video (select → tap → sheet → read aloud). A guards strip appears over the first seconds: *scripture and set poetry never sent to the model · numbers and negations checked in code, else keep the original sentence · read aloud on the device*. Lower strip appears at the end: "Xiaomi Mi 11X, Snapdragon 870, 6 GB". Two columns: **AraBART, default: 222 MB, first word 82–172 ms** · **AraT5v2 / model 3, optional: 471 MB, first word 177–318 ms**. Not the laptop latency.
- Say little: let the video run.

### Scene 8: Close and limits (0:17)
1. Logo, "Simplify where you read."
2. Three honest chips: **no reader has used the app, one reader rated outputs** · **the scorer is a model: stricter than people** · **simplifying more costs meaning**. Next (one line): "make the model simplify like the tagged setting and keep meaning like the safe one; run a reading study". Thanks.

## 4. Backup scenes (outside the clock, for Q&A; reachable by number)

| # | Backup | Content |
|---|---|---|
| B1 | Why not SAMER | SARI table copy vs model 1, identity 42/49%, 9.3% leakage in a public corpus |
| B2 | Meaning judge | 4-head Gemma 4 E2B, 95.5% planted errors, 86.5% human-labelled changes, ~62% subtle, 94% of teacher, ~30× faster |
| B3 | Corpus v0 audit | validator accepted 34% added and 25% deleted sentences at 0.7 |
| B4 | People, per system | same-meaning: AraT5 int8 94%, untagged 89%, tagged 77%, AraBART 71% |
| B5 | On-device table | full table and the int8 caveat |
| B6 | Diacritization | Libtashkeel 8.43% DER (6.91% without case endings), 4.8 MB, 0 base letters changed; CAMeL changed 32 of 100 |
| B7 | Limitations | full list from report 4.3 |
| B8 | Process | team roles, issue and PR workflow |
| B9 | The ship question | benchmark report ship gate vs Marwan's re-baseline (#58): the −8.1 [−13, −3], what "today's app" means (Sept vs `main` text step), beam 4 unscored pairs (#65); show whichever is settled by then |
| B10 | The app's text step | clean → protected → split → model → guards; numbers kept 72% → 100%, meaning +3.5 on dev; settings off by default (tashkeel, beam) |

## 5. Say carefully (replaces the old table)

| Do not say | Because |
|---|---|
| "It helps readers with dyslexia" | No reader has used it. Say "reduces reading load". |
| "The reader picks a strength" | The app sends no tag. |
| "Model 3 is the best" / "beats the current app on meaning" | Rewritten outputs, test: P(same) 0.69 vs 0.78 (paired −0.10 [−0.16, −0.03]). Say "simplifies the most" and show the cost. |
| "74% vs 48%" with no label | It is against the app as benchmarked on 4 Oct (September text step). Always label it. |
| "Fits 250 MB" for everything | Default 222 MB; 471 MB optional. |
| "Never changes meaning" | When model 3 rewrites, P(same) is 0.67 vs 0.74. |
| "Meaning judge validated" as a headline | AUC 0.85 on 245 rated outputs; ease and Arabic not validated. |
| SARI as a headline | Three protocols disagree; used only to show copy beats it. |
| Baseet by name, "13,072 rows", 22,733 as the corpus | Superseded in the report. |
| "No tool exists for Arabic dyslexia" | Only: our searches of 17 and 23 Sep found no Arabic + automatic + on-device system. |

## 6. Build order (submission Mon 5 Oct, pitch Tue 6 Oct)

1. **Facts (30 min).** Re-point `facts.py` at the new report commits; add the new figures above; `check_numbers.py` must pass. Resolve conflicts 1 and 2 with Marwan on #52.
2. **Script (30 min).** Rewrite `script_data.py` to the run sheet; regenerate both script and notes; check the word count against the clock.
3. **Scenes by value, rendered in parallel with `setsid nohup`:** 6 (Results), 5 (Measuring), then 4, 3, 2, 8, 7, 1. Each must pass `audit()` clean.
4. **Both decks.** Presenting HTML (`make_html.py`) and native pptx (`build_native.py`) read the same `script_data.py`. The native deck needs the new scenes 5 and 6 built as shapes (the cost lies here).
5. **Backups B1–B10** only after the core is done; B9, B2 and B7 first.
6. Rehearse once with a timer; assign speakers.

## 7. Assumptions
- 4:00 live (confirmed), backups for Q&A.
- Model 3 is shown as the strongest simplifier that costs the most meaning, as the paired 5 Oct figures show (−0.10 on test).
- Two speakers, split after scene 4.
