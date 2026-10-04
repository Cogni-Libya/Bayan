"""What is measured on each item (BayanBench v2, #48). Every measure is reported on its own, in blocks:

  meaning      the open meaning scorer's P(yes) for "same meaning" (meaning.py), and "meaning kept": P(same) at or
               above the frozen threshold, every number kept, and no flagged change the scorer calls a contradiction
  simpler      continuous changes from selection to output, each on the items where there is something to simplify
  checks       deterministic pass/fail: every number kept, house punctuation rules
  behaviour    CheckList-style probes outside the headline: easy text (C), protected text (F), cut-off endings (E1)
  flags        changes code can spot that may change the meaning (negations, limits, conditions). Never a failure on
               their own: a flagged pair fails "meaning kept" only if the scorer's "contradict" P is over its threshold
  diagnostics  the v1 measures under test; each is dropped if its AUC against the human ratings has a 95% interval
               that includes .5 (the rule agreed in #48 before the ratings)

Each function returns {measure: value, or None when the measure does not apply or cannot be measured yet}. Values are
True/False (reported as a rate) or numbers (reported as a mean; the names in CONTINUOUS)."""
from .ease import hard_words
from .text import (FULL_STOP, conditions, end_mark, limits, longest_clause, negations, norm, numbers, punct_only,
                   retention, rule_breaks)

MEANING = {
    "meaning kept": "P(same) at or above the frozen threshold, every number kept, no flagged contradiction",
    "P(same meaning)": "mean P(yes) the meaning scorer gives \"same meaning\" (copies count 1)",
}
SIMPLER = {
    "longest clause: words shorter": "words cut from the longest clause (selections with a clause over 15 words)",
    "reading level: levels lower": "BAREC levels the hardest sentence drops (selections at level 10+)",
    "hard words: fewer": "SAMER level 4-5 words removed (selections with any; needs --samer)",
}
CHECKS = {
    "numbers kept": "every number of the selection is in the output (selections with numbers)",
    "no house-rule break": "no tashkeel, «، لأن», «لو… ف» or filler join the selection did not have",
}
BEHAVIOUR = {
    "C: easy text left unchanged": "already-easy selections come back unchanged",
    "F: letters unchanged": "Quran, Bible, classical poetry: same letters (vowel marks may drop)",
    "F: exactly unchanged": "Quran, Bible, classical poetry: exactly the same, vowel marks included",
    "E1: end mark kept": "cut-off selections keep their ending (the cut sentence is not completed)",
}
FLAGS = {
    "negation changed": "a different count of negation words (selections or outputs with one)",
    "limit changed": "a limit changed: at least / at most / more than / less than / only (either side has one)",
    "condition changed": "a different count of condition words: إذا، لو، كلما، ما لم… (either side has one)",
}
DIAGNOSTICS = {
    "kept 60%+ of words": "v1: the output keeps at least 60% of the selection's words",
    "no clause over 15 words": "v1: every clause 15 words or fewer (long-clause, messy and 40+ word selections)",
    "negations kept": "v1: same count of negation words, as pass/fail (selections with a negation)",
    "mid-sentence full stop added": "a full stop inside a one-sentence selection (a rate, not an error)",
    "B: not left as copy": "long-clause selections: the output is not the selection unchanged",
}
BLOCKS = {"meaning": MEANING, "simpler": SIMPLER, "checks": CHECKS, "behaviour": BEHAVIOUR, "flags": FLAGS,
          "diagnostics": DIAGNOSTICS}
CONTINUOUS = {"P(same meaning)", *SIMPLER}
JOINT = "meaning kept and simpler"


def flags(src, out):
    """{flag: True/False, None when neither side has the phenomenon}."""
    r = {}
    for name, f in (("negation changed", negations), ("limit changed", limits), ("condition changed", conditions)):
        a, b = f(src), f(out)
        r[name] = (a != b) if (a or b) else None
    return r


def item_measures(it, out, scores=None, lex=None, levels=None, cfg=None):
    """{block: {measure: value}} for one item. scores: meaning.Scores or None (meaning not scored in this run);
    cfg: meaning.config() with the frozen thresholds (None where not frozen yet)."""
    src, tr, cfg = it["source"], it["track"], cfg or {}
    r = {b: {} for b in BLOCKS}
    if tr == "F":
        r["behaviour"] = {"F: letters unchanged": norm(out) == norm(src), "F: exactly unchanged": out.strip() == src.strip()}
        return r
    nums_ok = numbers(out) == numbers(src)
    br = rule_breaks(src, out)
    r["checks"] = {"numbers kept": nums_ok if numbers(src) else None,
                   "no house-rule break": not [b for b in br if b != FULL_STOP]}
    if tr == "C":
        r["behaviour"]["C: easy text left unchanged"] = norm(out) == norm(src)
    if tr == "E1":
        r["behaviour"]["E1: end mark kept"] = end_mark(out) == end_mark(src)
    r["flags"] = fl = flags(src, out)

    if scores is not None:
        p = scores.get(src, out)
        r["meaning"]["P(same meaning)"] = p["same"] if p else None
        t, tc = cfg.get("same_threshold"), cfg.get("contradict_threshold")
        if t is not None:
            if p is None:
                r["meaning"]["meaning kept"] = None
            else:
                contra = tc is not None and any(fl.values()) and p.get("contradict", 0) >= tc
                r["meaning"]["meaning kept"] = p["same"] >= t and nums_ok and not contra

    if tr != "C":
        ls = longest_clause(src)
        r["simpler"]["longest clause: words shorter"] = ls - longest_clause(out) if ls > 15 else None
        es, eo = (levels.get(src), levels.get(out)) if levels is not None else (None, None)
        r["simpler"]["reading level: levels lower"] = (es["level_max"] - eo["level_max"]
                                                        if es and eo and es["level_max"] >= 10 else None)
        hs = hard_words(src, lex) if lex is not None else 0
        r["simpler"]["hard words: fewer"] = hs - hard_words(out, lex) if hs else None
        r["diagnostics"]["kept 60%+ of words"] = retention(src, out) >= 0.6
        mins = cfg.get("simpler_min")
        if mins and "meaning kept" in r["meaning"]:
            sm = r["simpler"]
            applies = sm["longest clause: words shorter"] is not None or sm["reading level: levels lower"] is not None
            simpler = ((sm["longest clause: words shorter"] or 0) >= mins["clause_words"] and not punct_only(src, out)) \
                or (sm["reading level: levels lower"] or 0) >= mins["levels"]
            mk = r["meaning"]["meaning kept"]
            if applies:
                r["meaning"][JOINT] = None if mk is None else (mk and simpler)
    if tr in ("B", "E2", "E3"):
        r["diagnostics"]["no clause over 15 words"] = longest_clause(out) <= 15
    if negations(src):
        r["diagnostics"]["negations kept"] = negations(out) == negations(src)
    r["diagnostics"]["mid-sentence full stop added"] = FULL_STOP in br
    if tr == "B":
        r["diagnostics"]["B: not left as copy"] = norm(out) != norm(src)
    return r


# ---- v1 judge tier (Gemini 3.1 Pro verdicts), kept as an optional extra: `bayanbench score --gemini` ----
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
