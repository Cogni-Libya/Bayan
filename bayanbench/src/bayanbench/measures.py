"""What is measured on each item. Two tiers, reported side by side and never averaged:

  code   deterministic checks anyone can run anywhere (same outputs -> same score)
  judge  track pass rates that need a meaning / Arabic-quality verdict from an accepted judge

Each function returns {measure: True/False, or None when the measure does not apply to this item or cannot be
measured (no verdict yet, no SAMER lexicon, no reading level)}."""
from .ease import hard_words
from .text import end_mark, longest_clause, negations, norm, numbers, retention, rule_breaks

# name -> what it means (shown on the scorecard and the leaderboard)
CODE = {
    "numbers kept": "every number of the selection is in the output (items with numbers)",
    "negations kept": "same count of negation words (items with a negation)",
    "no house-rule break": "no mid-sentence full stop, tashkeel, «، لأن», «لو… ف», filler join the selection did not have",
    "kept 60%+ of words": "the output keeps at least 60% of the selection's words (a guard against dropping content)",
    "B: no clause over 15 words": "long-clause items: every clause of the output is 15 words or fewer",
    "B: not left as copy": "long-clause items: the output is not the selection unchanged",
    "E3: no clause over 15 words": "very long sentences (40+ words): every clause 15 words or fewer",
    "E2: no clause over 15 words": "messy text: every clause 15 words or fewer",
    "C: easy text left unchanged": "already-easy items come back unchanged",
    "E1: end mark kept": "cut-off selections keep their ending (no completing the cut sentence)",
    "F: letters unchanged": "Quran, Bible, classical poetry: same letters (vowel marks may drop)",
    "F: exactly unchanged": "Quran, Bible, classical poetry: exactly the same, vowel marks included",
    "fewer hard words": "fewer SAMER level 4-5 words than the selection (items with any; needs --samer)",
    "lower reading level": "a lower BAREC level than the selection (selections at level 10+)",
}

JUDGE = {
    "A1": "meaning kept, general (and numbers kept)",
    "A2": "meaning kept on hard spots: negation, numbers, conditions, cause, quantity, certainty",
    "A3": "meaning kept on high-stakes text: laws, rights, health, medicine",
    "B": "long clauses fixed without a meaning error",
    "B2": "fewer hard words without a meaning error (needs --samer)",
    "B3": "lower reading level without a meaning error",
    "C": "easy text: no meaning or Arabic error introduced",
    "D": "correct Arabic: no grammar/punctuation error and no house-rule break",
    "E1": "cut-off selections: meaning kept and ending kept",
    "E2": "messy text: meaning kept and numbers kept",
    "E3": "very long sentences: meaning kept",
    "E4": "several sentences at once: meaning kept",
}
OVERLAY = ("B2", "B3", "D")        # scored across the items of the other tracks, not on items of their own


def code_measures(it, out, lex=None, levels=None):
    src, tr = it["source"], it["track"]
    if tr == "F":
        return {"F: letters unchanged": norm(out) == norm(src), "F: exactly unchanged": out.strip() == src.strip()}
    m = {"numbers kept": numbers(out) == numbers(src) if numbers(src) else None,
         "negations kept": negations(out) == negations(src) if negations(src) else None,
         "no house-rule break": not rule_breaks(src, out)}
    if tr == "C":
        m["C: easy text left unchanged"] = norm(out) == norm(src)
    else:
        m["kept 60%+ of words"] = retention(src, out) >= 0.6
        if lex is not None:
            hs = hard_words(src, lex)
            m["fewer hard words"] = hard_words(out, lex) < hs if hs else None
        if levels is not None:
            es, eo = levels.get(src), levels.get(out)
            m["lower reading level"] = eo["level_max"] < es["level_max"] if es and eo and es["level_max"] >= 10 else None
    if tr == "B":
        m["B: no clause over 15 words"] = longest_clause(out) <= 15
        m["B: not left as copy"] = norm(out) != norm(src)
    if tr == "E1":
        m["E1: end mark kept"] = end_mark(out) == end_mark(src)
    if tr == "E2":
        m["E2: no clause over 15 words"] = longest_clause(out) <= 15
    if tr == "E3":
        m["E3: no clause over 15 words"] = longest_clause(out) <= 15
    return m


def judge_tracks(it, out, flags, lex=None, levels=None):
    """flags: (meaning major?, language major?) from verdicts.Verdicts.flags, or None if not judged yet.
    Returns {track: passed} for the item's own track and the overlays that apply to it. A track that applies but has
    no verdict yet is None (pending); a track that does not apply is left out."""
    src, tr = it["source"], it["track"]
    if tr == "F":
        return {}
    num_ok = numbers(out) == numbers(src)
    hs = hard_words(src, lex) if lex is not None and tr != "C" else 0
    es, eo = (levels.get(src), levels.get(out)) if levels is not None and tr != "C" else (None, None)
    b3 = bool(es and eo and es["level_max"] >= 10)
    if flags is None:
        r = {tr: None, "D": None}
        if hs: r["B2"] = None
        if b3: r["B3"] = None
        return r
    meaning, lang = flags
    r = {}
    if tr in ("A1", "A3"):
        r[tr] = not meaning and num_ok
    elif tr == "A2":
        r[tr] = not meaning and num_ok and negations(out) == negations(src)
    elif tr == "B":
        r[tr] = not meaning and longest_clause(out) <= 15
    elif tr == "C":
        r[tr] = not meaning and not lang
    elif tr == "E1":
        r[tr] = not meaning and end_mark(out) == end_mark(src)
    elif tr == "E2":
        r[tr] = not meaning and num_ok
    elif tr in ("E3", "E4"):
        r[tr] = not meaning
    r["D"] = not lang and not rule_breaks(src, out)
    if hs:
        r["B2"] = hard_words(out, lex) < hs and not meaning
    if b3:
        r["B3"] = eo["level_max"] < es["level_max"] and not meaning
    return r
