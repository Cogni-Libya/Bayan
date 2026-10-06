"""Single source for what the presenter says. `make_script.py` turns it into the printable
script; both decks take their speaker notes from it, so the notes cannot drift from the script.

One entry per beat. Each step is (what appears on screen, what to say). Every step waits for a
click (see build/README.md); start talking as the animation starts.

Every number comes from `facts.py` and is checked by `check_numbers.py`. Claims nothing supports
are listed in DONT_SAY. The scene plan with sources is `../SCENE_PLAN.md`.
"""

SPEAKERS = {1: "Sanad"}

# scene -> (beat title, steps). 4 minutes, one speaker (Sanad presents, per the WBS). Say “v zero point three”.
SPEECH = [{'scene': 'S1Cover',
  'speaker': 1,
  'title': 'Cover',
  'steps': [('The logo draws itself, then the title and team appear',
             'This is Bayan: an Android tool that simplifies hard Arabic where you read, on your phone. '
             'Building it was fine. Checking it was the hard part.')]},
 {'scene': 'S2Problem',
  'speaker': 1,
  'title': 'The problem',
  'steps': [('11% counts up; كتب splits into kataba, kutiba, kutub',
             "About eleven percent of Arab primary-school children have dyslexia, and Arabic doesn't help: "
             "these letters can be kataba, kutiba or kutub, because short vowels aren't written."),
            ('Left: shorter clauses help the weakest readers most. Right: our scope',
             'Shorter clauses help the weakest readers most. So Bayan reduces reading load: long clauses, '
             "hard words. Tashkeel is a setting in the app, and we don't yet claim it helps readers with dyslexia.")]},
 {'scene': 'S3Data',
  'speaker': 1,
  'title': 'Data: how we got to corpus v1',
  'steps': [('Two cards: SAMER (novels, half unchanged, word swaps) and other LLM-written sources '
             '(summaries)',
             'We started with what existed. SAMER is novels: half its pairs are unchanged, and it swaps '
             'words but never splits sentences. The other sources mostly summarised.'),
            ('Corpus v0: DeepSeek -> validator -> readability gate; three red chips; validator accepted 34% '
             'of planted additions',
             'So we wrote our own with DeepSeek. The audit was humbling: tashkeel in fifty-seven percent of '
             'rows, cut-off sentences helpfully completed, a validator that waved through a third of our '
             'planted errors. We trained nothing on it.'),
            ('Pipeline v1: BAREC -> strip tashkeel -> route -> Gemma 4 31B -> code, readability and meaning '
             'gates',
             'Corpus v1 starts from BAREC, strips tashkeel, sets protected and short text aside, and has '
             'Gemma 4 31B rewrite the hard sentences behind three gates.'),
            ('14,975 rows lock in; audit badge: 1.7% meaning changed',
             'Fourteen thousand nine hundred seventy-five pairs survived. A blind audit found one point '
             "seven percent with changed meaning. We'll take it.")]},
 {'scene': 'S4Models',
  'speaker': 1,
  'title': 'BayanSimplify versions',
  'steps': [('Lane v0.1: AraT5v2 on SAMER. Found: returned 65% of rows unchanged, swapped single words',
             'BayanSimplify v0.1 trained on SAMER. It returned sixty-five percent of sentences untouched, '
             'where editors leave forty-nine. Bold strategy: change nothing.'),
            ('Lane v0.2: two models, AraT5v2 (v0.2) and AraBART (v0.2-Fast); meaning kept 60% / 40%; the tag '
             'costs meaning',
             'v0.2 is two models, AraT5v2 and AraBART, trained with everyday text and strength tags. They '
             'kept the meaning in sixty and forty percent of outputs. The tag costs meaning, so the app '
             'sends none.'),
            ('Lane v0.3: AraT5v2 on corpus v1, our best: cuts 9.5 words vs 4.5, about the same meaning (vs '
             'v0.2, no tag)',
             'v0.3 is AraT5v2 on corpus v1, no tag. As trained, it cuts twice the words of v0.2 and keeps '
             'about the same meaning.')]},
 {'scene': 'S5Measure',
  'speaker': 1,
  'title': 'Measuring it, and the people check',
  'steps': [('Copy baseline table: copy 100% / 0; v0.1 76% / 0; v0.2 68% / 4.5 and v0.2-Fast 51% / 4.9; v0.3 '
             '69% / 9.5',
             'How do we know a rewrite is good? Copying keeps all the meaning and simplifies nothing, which '
             'is how a lazy model would win. v0.1 nearly managed it: seventy-six percent kept, no words cut '
             'from the longest clause. So we built BayanBench.'),
            ('Gemma 4 31B reads original + rewrite and answers 7 yes/no questions: 4 on meaning, 3 on '
             'quality',
             'Meaning comes from Gemma 4 31B, an open model. It reads the original and the rewrite and '
             'answers seven yes-or-no questions: four about meaning, three about quality.'),
            ('Four measures in a square: meaning, simpler, restraint, copying rate',
             'Four measures, scored separately. Kept means the same meaning and every number intact.'),
            ('People check: one reader with dyslexia rated 30 outputs (17 easier, 9 same, 4 harder); scorer '
             'AUC 0.85',
             'Do people agree with the scorer? Six raters, two hundred ninety tasks: zero point eight five. '
             'One reader with dyslexia rated thirty outputs too: seventeen easier, four harder.')]},
 {'scene': 'S6Results',
  'speaker': 1,
  'title': 'Results: v0.3 is our best',
  'steps': [('Scatter: v0.3 in the app keeps the most meaning (82%) and cuts 5.2 words',
             'More simplification usually means less meaning. v0.3 breaks the pattern: in the app it keeps '
             'the most meaning, eighty-two percent, and still cuts five words off the longest clause.'),
            ('In the app: v0.3 minus v0.2 behind the same checks: +3.4 words, harder words out, meaning kept '
             'as well (not significant)',
             'Against v0.2 behind the same checks, it cuts three and a half more words off the longest '
             'clause, removes more hard words, and keeps the meaning as well. Not significantly different.'),
            ('Blind rating, 18 sentences: v0.3 easier on 86% of changed outputs vs 60%; 8 of 8 votes',
             "People agree. In a blind rating, the team found v0.3's changed outputs easier eighty-six "
             'percent of the time, against sixty for v0.2, and the reader with dyslexia chose v0.3 in every '
             'comparison it was in.')]},
 {'scene': 'S7Phone',
  'speaker': 1,
  'title': 'On a phone',
  'steps': [("Heading 'What the app does' and the video recording under it",
             'On a phone: select, tap tabseet, and it reads aloud. Scripture never reaches the model, and '
             'code checks that numbers survive.')]},
 {'scene': 'S8Close',
  'speaker': 1,
  'title': 'Close',
  'steps': [("Logo and 'Simplify where you read.'", 'Bayan: simplify where you read.'),
            ('Three limit chips and the next step',
             "What we can't claim: no reader has used it, our scorer is stricter than people, and our human "
             'comparison is eighteen sentences. Next, a reading study. Thank you!')]}]

# Things the slides or the room might tempt you to say that nothing we have supports.
DONT_SAY = [
    ("“It helps readers with dyslexia” / “it improves reading”",
     "No reader has used Bayan. One reader with dyslexia rated 30 outputs for ease (17 easier, 9 same, "
     "4 harder). Say “reduces reading load”."),
    ("“Model 1 / 2 / 3”",
     "The models are BayanSimplify v0.1, v0.2 (AraT5v2), v0.2-Fast (AraBART) and v0.3, named on Hugging Face "
     "(issue #68, README 3a). v0.3 is the app's large model; v0.2 is the “earlier large model”."),
    ("“The reader picks a strength”",
     "The app sends no strength tag, and the tag costs meaning: untagged v0.2 keeps 68.3% against 59.5% tagged."),
    ("“v0.3 keeps more meaning than v0.2”",
     "Behind the same text step the difference is −3 points [−7, +1], not significant. Say “keeps the meaning as well”. "
     "The earlier “−8 points” was greedy decoding on partly scored data and was withdrawn (#68)."),
    ("“v0.3 copies less”",
     "A teammate's count (unverified here) has v0.3 with four beams leaving 46% of core test items unchanged against "
     "32% for v0.2 in the app. A copy counts as perfect meaning, so say nothing about copying."),
    ("“Today's app” for old comparisons",
     "Numbers measured before 4 October used the September text step (v0.2, 18.8% of items unchanged). "
     "The current baseline is v0.2 behind the newest text step."),
    ("“It fits in 250 MB”",
     "The default v0.2-Fast bundle is 222 MB; the AraT5v2 bundles (v0.2, v0.3) are 471 MB."),
    ("“Bayan adds diacritics” as a benefit",
     "Libtashkeel is in the app as a setting, off by default, and untested with readers. We strip tashkeel "
     "before the model."),
    ("“Copying scored higher than our model” as a headline",
     "SAMER SARI is scored under several protocols that disagree. Use the behaviours (copy rate 65% vs "
     "editors' 49%), not SARI."),
    ("“The judge is validated” as a headline",
     "AUC 0.85 on 245 rated outputs. Only meaning is rated consistently enough; ease (α 0.19) and Arabic "
     "(α 0.17) are not validated."),
    ("“The reader found v0.3 easiest”",
     "On single outputs the reader found 4 of 6 v0.3 outputs easier, 2 of 6 for v0.2 and 5 of 6 for v0.2-Fast. "
     "Only in head-to-head comparisons did they choose v0.3 every time (4 of 4). Six per model: anecdote."),
    ("“The people comparison proves v0.3 is better”",
     "It is 18 sentences, blind, team raters (86% vs 60% easier, 8 of 8 votes): a direction, not a size."),
    ("“No Arabic dyslexia tool simplifies text” / “none is made for dyslexia”",
     "Only: our searches of 17 and 23 September found no system combining Arabic, automatic rewriting and "
     "on-device inference."),
    ("“Our training set was 22,733 pairs” / “13,072 rows” / anything about Baseet",
     "Superseded by corpus v1, 14,975 rows. The report names Baseet once, in its tables."),
]

# (question, answer, where it comes from). Keep answers short enough to say in 20 seconds.
QA = [
    ("What exactly does Bayan claim?",
     "It reduces linguistic load (long clauses, hard words) and reads aloud, in any app, on the phone. "
     "Not decoding, layout or fluency; none of those are tested with readers.",
     "report 1.2, scope paragraph"),
    ("Is v0.3 better than v0.2?",
     "On simplicity yes: 3.4 more words cut from the longest clause [2.4, 4.4], 18 points more easy text left "
     "unchanged, every number kept, and meaning kept as well (−3 points [−7, +1], not significant). In a blind "
     "rating of 18 sentences it was found easier on 86% of changed outputs against 60%, and won 8 of 8 team votes.",
     "issue #68; report 3.2"),
    ("What did the reader with dyslexia say about v0.3?",
     "In the 24-task round they chose v0.3 in all 4 comparisons it was in (2 of 2 against v0.2, 2 of 2 against v0.2-Fast). "
     "On single outputs, 4 of 6 v0.3 outputs were easier and none harder, against 2 of 6 for v0.2 and 5 of 6 for v0.2-Fast. "
     "Six outputs per model is anecdote, not a measurement.",
     "report 3.1; human_m3.tex"),
    ("Doesn't it just copy more?",
     "A teammate's count has v0.3 leaving more items unchanged (46% vs 32%, unverified here), and a copy counts "
     "as perfect meaning. That is why the benchmark reports easy text left alone separately, and why we also asked people.",
     "peer figures 5 Oct"),
    ("What did you try that did not work?",
     "Student DPO, minimum-risk training and a fluency retrain: none beat v0.3 on the 31B scorer, so we dropped them.",
     "benchmark report 1"),
    ("What does “meaning kept” mean?",
     "P(same meaning) at or above 0.5 from Gemma 4 31B, and every number in the input still in the output. "
     "The threshold was set before the human ratings and kept after.",
     "report 2.5"),
    ("How good is the meaning scorer?",
     "AUC 0.85 against the human majority on 245 rated outputs. It catches 42 of the 51 outputs raters "
     "judged changed, all 11 major ones, but fails 53 of 194 they kept: stricter than people.",
     "report 3.1"),
    ("Did readers with dyslexia test it?",
     "No one has used the app. One reader with dyslexia rated 30 outputs for ease: 17 easier, 9 the same, "
     "4 harder. A reading study is next.",
     "report 3.1, limitations"),
    ("How big and how fast is it on a phone?",
     "The fast model, v0.2-Fast: 222 MB, first word in 82 to 172 ms on a Xiaomi Mi 11X. The large models "
     "(v0.2, v0.3): 471 MB, first word 177 to 318 ms. v0.3 with four beams writes a sentence in about 1.2 s.",
     "report 3.6"),
    ("Why did you drop the strength tags?",
     "The app never sent them, and untagged outputs kept meaning better: 68.3% against 59.5% for v0.2.",
     "report F1, F5"),
    ("How do you know the training data is clean?",
     "Corpus v1 is built from BAREC behind code, readability and meaning gates; 0 rule violations, 0 leakage "
     "against BAREC test, and a blind audit of 1,039 pairs found 1.7% with changed meaning.",
     "report 2.1"),
    ("What stops it breaking numbers or scripture?",
     "The app's text step, in code: scripture and set poetry never reach the model, and a sentence reverts "
     "to the source if a number, negation or Latin word is lost. Numbers kept 72% → 100% on dev.",
     "report 2.4"),
    ("Is the data legal to use?",
     "SAMER is used under CAMeL Lab's written approval for non-commercial research and never redistributed. "
     "Corpus v1 is our own synthetic data, published.",
     "report 2.1"),
    ("Why not SARI?",
     "Half of SAMER needs no change, so copying scores high and SARI rewards inaction. We report behaviours "
     "and a copy baseline beside every score.",
     "report 3.1 (RQ1)"),
]

CHECKLIST = [
    "Run `python check_numbers.py` in build/. It must say all numbers sourced before you render. Peer-session "
    "figures are flagged UNVERIFIED: confirm them on issue #65 or #58.",
    "Open `Bayan_Presenting.html` in Chrome on the presenting laptop once, and click through every step. "
    "Every step waits for a click.",
    "Or run `manim-slides present S1Cover S2Problem S3Data S4Models S5Measure S6Results S7Phone S8Close` "
    "from build/ as the live player.",
    "Record the 30 s phone video and drop it into the S7Phone slot (see README); play it once, audio off.",
    "Print this script or keep it on a second screen; both decks carry the same text in their notes.",
    "Time yourself out loud once. Target 3:45 to 4:00.",
    "Native deck only: it still shows the 5 October content until it is rebuilt (see README).",
    "Bring the HTML file on a USB stick as a last resort; it needs no install.",
]

CUTS = [  # in this order, if running long
    "Scene 2 step 1: drop the كتب readings, keep the 11%: about 6 s.",
    "Scene 3 step 1: keep only “our first synthetic data was wrong, so we rebuilt it”: about 6 s.",
    "Scene 4 step 3: drop the spoiler: about 3 s.",
    "Scene 5 step 2: shorten to “Gemma 4 31B answers seven yes-or-no questions”: about 5 s.",
    "Scene 7: stay silent and let the video play: about 14 s.",
]

WPM = 130  # comfortable speaking pace for a prepared pitch; includes no pauses


def words(text):
    return len(text.split())


def slide_notes(scene):
    """Whole-slide notes for the native deck: one paragraph per step."""
    s = next(x for x in SPEECH if x["scene"] == scene)
    out = [f"[{SPEAKERS[s['speaker']]}]"]
    for k, (cue, text) in enumerate(s["steps"], 1):
        head = "on arrival" if k == 1 else f"step {k} (auto)"
        out.append(f"▶ Step {k} ({head}; {cue})\n{text}")
    return "\n\n".join(out)


def step_notes(scene, k):
    """Notes for one step of the presenting deck (one slide per step)."""
    s = next(x for x in SPEECH if x["scene"] == scene)
    cue, text = s["steps"][k - 1]
    head = f"[{SPEAKERS[s['speaker']]}] " if k == 1 else ""
    return f"{head}Step {k} of {len(s['steps'])} ({cue})\n{text}"
