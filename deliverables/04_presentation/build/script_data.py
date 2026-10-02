"""Single source for what the presenters say. `make_script.py` turns it into the printable script; both decks take their
speaker notes from it, so the notes cannot drift from the script.

One entry per slide. Each step is (what appears on screen, what to say). Step 1 of a slide plays by itself when the
slide appears; every further step needs one click (or right arrow). Start talking as the animation starts.

Every number is from Bayan_Final_Report.pdf (28 Sep 2026). Claims the report does NOT support are listed in DONT_SAY.
"""

SPEAKERS = {1: "Speaker 1", 2: "Speaker 2"}

SPEECH = [
    {"scene": "S1Cover", "speaker": 1, "title": "Cover", "steps": [
        ("The logo draws itself, then the title and team appear",
         "Hello everyone, we are Team Cogni. This is Bayan: an Android tool that makes hard Arabic easier to read for "
         "people with dyslexia, entirely on the phone. I cover the idea, the verdict and the data; my colleague "
         "covers the training."),
    ]},
    {"scene": "S2Problem", "speaker": 1, "title": "The problem", "steps": [
        ("11% counts up",
         "About eleven percent of Arab primary-school children have developmental dyslexia."),
        ("كتب splits into three readings",
         "Arabic makes reading harder in three ways. First, short vowels are not written: these three letters can be "
         "kataba, he wrote; kutiba, it was written; or kutub, books."),
        ("Two barrier chips appear",
         "Second, prefixes and suffixes fuse into long words. Third, clauses chain into sentences longer than working memory."),
    ]},
    {"scene": "S3Gap", "speaker": 1, "title": "The gap", "steps": [
        ("Table: who writes the rewrites, and how often a sentence is split",
         "What already exists? Four public corpora, and they almost never split a long sentence: zero percent of SAMER "
         "pairs, two to four percent of Baseet, eight percent of DAASI."),
        ("Red row: Made for dyslexia: no, no, no, no",
         "None of them is made for dyslexia."),
        ("Conclusion line",
         "No deployed Arabic dyslexia tool simplifies text, and no open corpus fits. So we built our own data, our own "
         "models, and our own benchmark."),
    ]},
    {"scene": "S4Verdict", "speaker": 1, "title": "The verdict", "steps": [
        ("Three options A, B, C",
         "Our verdict. A Chrome extension is desktop-first, but people read on phones. A standalone app makes the "
         "reader copy, paste, and leave what they were reading."),
        ("Phone demo: text is selected, the menu shows تبسيط, a result sheet slides up",
         "So Bayan is an Android plugin. Select hard text in any app, tap tabseet, which means simplify, and a sheet "
         "shows the simpler text and reads it aloud."),
        ("Option B is highlighted; on-device, offline, 250 MB chips",
         "We decided on the twentieth of September. Everything runs on the phone, offline: the reader's text never "
         "leaves it, in about two hundred fifty megabytes."),
    ]},
    {"scene": "S5Data", "speaker": 1, "title": "Data", "steps": [
        ("9.3% appears",
         "Before training, we audited the public data. Nine point three percent of Baseet overlapped our locked test "
         "sets, so every training file now passes a leakage gate."),
        ("Stacked bar of 22,733 pairs with the legend",
         "Our training set has twenty-two thousand seven hundred thirty-three pairs, each tagged with its source style. "
         "We keep SAMER's unchanged pairs, so the model learns when not to edit."),
        ("Meaning-filter line",
         "LLM-written Baseet pairs get in only through a meaning filter calibrated on human-verified rewrites. My "
         "colleague will show what we trained on it."),
    ]},
    {"scene": "S6Candidates", "speaker": 2, "title": "Two candidates, one recipe", "steps": [
        ("Recipe card: one script, identical data, 10 epochs, fp16, seed 42",
         "One recipe for every model: same script, same data, a fixed seed, and checkpoints chosen on rows a human changed."),
        ("Three bars: AraT5v2, AraBART, HPLT T5",
         "Two architectures. AraT5v2 has three hundred sixty-eight million parameters; AraBART one hundred thirty-nine "
         "million, two point six times smaller, so it is our on-device contender. HPLT T5 is held in reserve."),
        ("46% line",
         "Nearly half of AraT5v2 is two embedding tables, so shrinking its vocabulary matters for the phone."),
    ]},
    {"scene": "S7Model1", "speaker": 2, "title": "Model 1", "steps": [
        ("Left chart: all rows. Copy 77.50, Model 1 75.88. Text: Copying wins?",
         "Model 1 first looked like a failure. On all test rows, copying scores seventy-seven point five and our model "
         "seventy-five point nine. But half these sentences need no change, so doing nothing scores well."),
        ("Right chart: changed rows. Copy 56.06, Model 1 61.83",
         "On the rows a human changed, copying scores fifty-six point one and Model 1 sixty-one point eight: nearly six "
         "points better, with the greedy decoding the phone uses. But it mostly made one-word edits."),
    ]},
    {"scene": "S8Model2", "speaker": 2, "title": "Model 2", "steps": [
        ("Lesson 1 and its fix",
         "Model 2 answers each lesson. One: Model 1 rewarded doing nothing, so we keep every unchanged pair and choose "
         "checkpoints on changed rows."),
        ("Lesson 2 and its fix",
         "Two: SAMER teaches word swaps, so we add everyday and educational text, through the meaning filter."),
        ("Lesson 3 and its fix",
         "Three: one strength fits no one, so every source carries a tag."),
        ("Five tags [S0] to [SA]; the sun marks the default, [S2]",
         "Zero is minimal, one light, two medium, the default we score, three strong, A everyday. Each tag is meant to "
         "become the reader's strength setting."),
    ]},
    {"scene": "S9Close", "speaker": 2, "title": "Close", "steps": [
        ("Logo and 'Simplify where you read.'",
         "Bayan: simplify where you read."),
        ("Next: does it work? Three chips, then the SIC slogan",
         "Next: does it work? BayanBench, our benchmark for the reader's task; tests on a real phone; and evidence from "
         "readers with dyslexia. Thank you, and thanks to Samsung Innovation Campus. Questions welcome."),
    ]},
]

# Things the slides or the room might tempt you to say that the report does not support (as of 28 Sep 2026).
DONT_SAY = [
    ("“Readers with dyslexia tested it” / “it improves reading”",
     "No reader has used Bayan yet. The human evaluation (O4) is not started; every result is automatic (report 4.3, Table 18)."),
    ("“Bayan adds diacritics”",
     "Libtashkeel is chosen and benchmarked (DER 6.91% without case endings, 4.8 MB) but is not in the app yet (O2 in progress)."),
    ("“The app lets you pick a strength”",
     "The design does, but the app does not send the strength tag yet (Table 17, F5, not started)."),
    ("“AraT5v2 fits on the phone”",
     "The AraT5v2 int8 bundle is 471 MB; vocabulary pruning is in progress. AraBART int8 is 222 MB and is in the app."),
    ("“Model 2 beats Model 1 on the test sets”",
     "Test-set SARI tables and the judge tier are still pending (#30). Model 2's 66.58 is on changed dev rows, not test."),
    ("“It never changes meaning”",
     "It edits easy text that should be left alone, rewrites protected scripture, and drops Persian-range digits; "
     "fixes are planned, not done (Table 17, F3 and F4)."),
]

# (question, answer, where it comes from). Keep answers short enough to say in 20 seconds.
QA = [
    ("Why on the phone and not a server?",
     "The reader's text never leaves the phone and it works offline. The budget is about 250 MB; the AraBART int8 bundle is 222 MB.",
     "report 1.2 O3, 4.4; Table 18"),
    ("Why AraBART, when AraT5v2 scored higher?",
     "On the dev selection sample AraT5v2 scored 66.58 SARI and AraBART 64.71. AraBART is 2.6 times smaller and generates "
     "about 3.6 times faster, and its int8 bundle fits the budget; AraT5v2's is 471 MB.",
     "README section 4; Table 17"),
    ("Why is SARI not enough?",
     "Copying the input scores 77.5 on SAMER test, because half the rows need no change. So we report the changed rows "
     "separately (56.06 for copying) and built BayanBench for behaviour.",
     "report 3.3"),
    ("What is BayanBench?",
     "A behavioural benchmark: 1,981 items in 13 tracks, split by document, each measure reported separately with a "
     "cluster-bootstrap interval. Code checks and LLM-judge verdicts are kept apart.",
     "report abstract, 2.5"),
    ("How do you know the training data does not leak into the tests?",
     "We audited Baseet and found 9.3% overlapped the SAMER and BAREC test sets, removed those rows, and every training "
     "file must pass a leakage check. Both training sets were checked against both locked test sets on 21 September.",
     "report 3.1; README section 3"),
    ("How do you keep the meaning?",
     "Training: Baseet pairs pass a filter (LaBSE ≥ 0.646, length ≥ 67%, numbers kept), with thresholds from human-verified "
     "rewrites. Evaluation: a judge that is kept away from data it produced. The app shows the original one tap away.",
     "report 2.2, 4.4"),
    ("What are the known failures?",
     "Model 2 edits easy text that should be left alone, rewrites protected scripture, and drops Persian-range digits. "
     "Each has a planned fix (protected-text detection, digit mapping).",
     "report abstract, Table 17"),
    ("Did you test it with readers with dyslexia?",
     "Not yet. A blind 100-item rating set and page are prepared; sessions will run with informed consent. Until then "
     "every result is automatic, and we say so.",
     "report 4.3, Table 18"),
    ("How fast is it on a phone?",
     "On a Snapdragon 870, the first token of a sentence arrives in 55–318 ms (AraT5v2 int8). Release-build "
     "AraBART timing is still to be measured.",
     "Table 18; 4.2"),
    ("Is the data legal to use?",
     "SAMER is used under CAMeL Lab's written approval to fine-tune and publish weights non-commercially, and is never "
     "redistributed. The corpus we published is our own synthetic data (13,072 rows).",
     "report 2.1, 4.4"),
]

CHECKLIST = [
    "Decide which deck you present: Bayan_Presenting.pptx (Manim videos) or Bayan_Submission.pptx (native). Do not mix.",
    "Open the deck on the presenting laptop at least once, in slide-show mode, and click through every step.",
    "Presenting deck: confirm each slide's video autoplays. If not, the slide still shows its finished state; or use "
    "`manim-slides present` from build/ as the live fallback.",
    "Native deck: install the fonts Readex Pro, Noto Naskh Arabic and Amiri on that laptop, or the text will reflow.",
    "Put the speaker notes on a second screen or print this script; both decks carry the same text in their notes.",
    "Agree the handoff after slide 4 and who answers which question. Time yourselves out loud once.",
    "Bring a PDF of the deck as a last resort (Bayan_Presenting_static.pdf shows every step's final frame).",
]

CUTS = [  # in this order, if running long
    "Slide 6, step 3 (the 46% line): about 6 s. Keep it for Q&A.",
    "Slide 3, step 1: drop the three percentages, keep “they almost never split a long sentence”: about 6 s.",
    "Slide 5, step 3: keep only the handoff sentence: about 5 s.",
    "Slide 7, last sentence (“But it mostly made one-word edits”): about 3 s.",
]

WPM = 130  # comfortable speaking pace for a prepared pitch; includes no pauses


def words(text):
    return len(text.split())


def slide_notes(scene):
    """Whole-slide notes for the native deck: one paragraph per step."""
    s = next(x for x in SPEECH if x["scene"] == scene)
    out = [f"[{SPEAKERS[s['speaker']]}]"]
    for k, (cue, text) in enumerate(s["steps"], 1):
        head = "on arrival" if k == 1 else f"click {k - 1}"
        out.append(f"▶ Step {k} ({head}; {cue})\n{text}")
    return "\n\n".join(out)


def step_notes(scene, k):
    """Notes for one step of the presenting deck (one slide per step)."""
    s = next(x for x in SPEECH if x["scene"] == scene)
    cue, text = s["steps"][k - 1]
    head = f"[{SPEAKERS[s['speaker']]}] " if k == 1 else ""
    return f"{head}Step {k} of {len(s['steps'])} ({cue})\n{text}"
