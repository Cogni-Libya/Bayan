"""Deterministic, code-level constraints on (source, simplification) pairs -- the half of each rule in
issue #44 that doesn't depend on the generator obeying its prompt.

Used in two places with the same functions, so the gate and the audit can't drift apart:
  - barec_simplification_pipeline.py: routing (protected / short), candidate normalization before
    scoring, and the hard structure gates a candidate must pass to be eligible;
  - check_corpus.py: the post-export audit, which must report zero violations.

Character classes are written with \\u escapes, not literal Arabic marks: combining marks reorder when
copied from rendered text, and a literal range built that way silently swallowed the whole Arabic
letter block once already.
"""
from __future__ import annotations

import re

# Tashkeel (harakat, tanween, shadda, sukun, dagger alef, Quranic annotation marks) and tatweel.
TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
ARABIC_LETTER = "ء-يٱ-ۓ"
WORD = re.compile(f"[{ARABIC_LETTER}0-9٠-٩]+")
SHORT_MAX_WORDS = 5


def strip_tashkeel(text: str) -> str:
    return TASHKEEL.sub("", text)


def word_count(text: str) -> int:
    return len(WORD.findall(strip_tashkeel(text)))


def is_short(text: str) -> bool:
    return word_count(text) <= SHORT_MAX_WORDS


# --- quiz / multiple choice --------------------------------------------------------------------

# An option label: "(أ)" anywhere, or a bare "أ)" / "أ-" starting a token. Only the first five letters
# of the abjad order are used as labels in BAREC's curriculum/MMLU items.
_LABEL_LETTERS = "أبجده"
OPTION_LABEL = re.compile(rf"\(\s*([{_LABEL_LETTERS}])\s*\)|(?<!\S)([{_LABEL_LETTERS}])\s*[)\-](?=\s)")
# "اختر" (choose) only as its own token: as a bare substring it also matches اختراع/اخترق/اخترت.
QUIZ = re.compile(
    rf"\(\s*[{_LABEL_LETTERS}]\s*\)|(?<!\S)[{_LABEL_LETTERS}]\s*[)\-]\s"
    rf"|(?<![{ARABIC_LETTER}])اختر(?![{ARABIC_LETTER}])"
    r"|ضع علامة|ضع دائرة|صح أم خطأ|صواب أم خطأ|أكمل الفراغ|…{2,}|\.{4,}"
)


def option_labels(text: str) -> list[str]:
    return [a or b for a, b in OPTION_LABEL.findall(strip_tashkeel(text))]


def is_quiz(text: str) -> bool:
    return bool(QUIZ.search(strip_tashkeel(text)))


def options_preserved(source: str, candidate: str) -> bool:
    """A multiple-choice source (2+ labels) must keep the same labels, in the same order: merging the
    options into prose, or dropping one, fails. Sources without options always pass."""
    src = option_labels(source)
    return len(src) < 2 or option_labels(candidate) == src


# --- scripture and honorifics ------------------------------------------------------------------

VERSE_MARKER = re.compile(r"﴿|﴾|قال (?:الله )?تعالى|قوله تعالى|قال (?:الله )?عز وجل|قال (?:الله )?سبحانه")
VERSE_SPAN = re.compile(r"﴿([^﴾]*)﴾")


def has_verse_marker(text: str) -> bool:
    return bool(VERSE_MARKER.search(strip_tashkeel(text)))


def _ws(text: str) -> str:
    return " ".join(text.split())


def verses_preserved(source: str, candidate: str) -> bool:
    cand = _ws(strip_tashkeel(candidate))
    return all(_ws(span) in cand for span in VERSE_SPAN.findall(strip_tashkeel(source)))


_END = rf"(?![{ARABIC_LETTER}])"  # so عنه doesn't also count inside عنهم/عنها/عنهما
HONORIFICS = {
    "salla": re.compile(r"صلى الله عليه وسلم|ﷺ"),
    "alayhi_salam": re.compile(rf"عليه السلام{_END}|عليهم السلام{_END}|عليها السلام{_END}"),
    "alayhi_salat": re.compile(r"عليه الصلاة والسلام|عليه أفضل الصلاة والسلام"),
    "radiya_anhu": re.compile(rf"رضي الله عنه{_END}"),
    "radiya_anha": re.compile(rf"رضي الله عنها{_END}"),
    "radiya_anhum": re.compile(rf"رضي الله عنهم{_END}|رضي الله عنهما{_END}"),
    "karrama": re.compile(r"كرم الله وجهه"),
    "azza_wa_jal": re.compile(r"عز وجل"),
    "subhanahu": re.compile(r"سبحانه وتعالى"),
    "jalla_jalaluh": re.compile(r"جل جلاله"),
}


def honorific_counts(text: str) -> dict[str, int]:
    plain = strip_tashkeel(text)
    return {name: len(p.findall(plain)) for name, p in HONORIFICS.items()}


def honorifics_preserved(source: str, candidate: str) -> bool:
    """Every honorific in the source appears at least as often in the candidate. A sentence split in
    two may legitimately repeat one, so >= rather than ==."""
    cand = honorific_counts(candidate)
    return all(cand[k] >= n for k, n in honorific_counts(source).items())


# --- sentence endings --------------------------------------------------------------------------

_CLOSERS = "\"'»”’)]}"
_STOP = ".!?؟"
_OPEN_ENDS = {"،": "،", ",": "،", "؛": "؛", ";": "؛", ":": ":"}


def _split_tail(text: str) -> tuple[str, str]:
    """(body, trailing closing quotes/brackets) with surrounding whitespace removed."""
    text = text.rstrip()
    i = len(text)
    while i > 0 and text[i - 1] in _CLOSERS:
        i -= 1
    return text[:i].rstrip(), text[i:]


def source_ending(text: str) -> str:
    """'stop' (. ! ? ؟), one of '،' '؛' ':' (the sentence continues), 'ellipsis', or 'none'."""
    body, _ = _split_tail(text)
    if not body:
        return "none"
    last = body[-1]
    if last in _STOP:
        return "ellipsis" if body.endswith("...") else "stop"
    if last == "…":
        return "ellipsis"
    return _OPEN_ENDS.get(last, "none")


def normalize_ending(source: str, candidate: str) -> str:
    """Make a cut-off source's simplification end the way the source does: a source that stops at
    «،», «؛» or «:» gets that mark instead of a full stop, and one with no final mark gets none -- so
    the pair never teaches "finish the selection". Sources that end a sentence, or end in an ellipsis
    (fill-in-the-blank), leave the candidate untouched."""
    kind = source_ending(source)
    if kind in ("stop", "ellipsis"):
        return candidate.strip()
    body, closers = _split_tail(candidate)
    if body.endswith("…") or body.endswith("..."):
        return candidate.strip()
    while body and (body[-1] in _STOP or body[-1] in _OPEN_ENDS):
        body = body[:-1].rstrip()
    return body + ("" if kind == "none" else kind) + closers


def normalize_candidate(source: str, candidate: str) -> str:
    """What actually ships: no tashkeel/tatweel, single spaces within lines, the source's ending."""
    text = strip_tashkeel(candidate)
    text = "\n".join(" ".join(line.split()) for line in text.strip().splitlines() if line.strip())
    return normalize_ending(source, text)


# --- readability units ---------------------------------------------------------------------------

SENTENCE_BREAK = re.compile(r"(?<=[.!?؟])\s+|\n+")


def mcq_stem(text: str) -> str:
    """The question part of a multiple-choice item (everything before its first option label); the text
    itself when it has no options. Options are copied through by design, so they carry no readability gain."""
    labels = list(OPTION_LABEL.finditer(text))
    return text[:labels[0].start()].strip() or text if len(labels) >= 2 else text


def readability_units(text: str) -> list[str]:
    """The sentences a rewrite is scored by: the MCQ stem, split after . ! ? ؟ and at line breaks.
    CAMeL is a sentence-level model (BAREC annotates single sentences), so a rewrite that splits one long
    sentence into several short ones is scored per sentence rather than as one long text."""
    units = [u.strip() for u in SENTENCE_BREAK.split(mcq_stem(text)) if u.strip()]
    return units or [text]


def structure_gates(source: str, candidate: str) -> dict[str, bool]:
    """The hard, deterministic gates a candidate must pass to be eligible at all."""
    return {
        "options_preserved": options_preserved(source, candidate),
        "honorifics_preserved": honorifics_preserved(source, candidate),
        "verses_preserved": verses_preserved(source, candidate),
    }
