"""Text helpers: normalisation, clause length, the automatic checks, and a port of the app's pipeline
(app/.../engine/ArabicText.kt + Simplifier.kt), so a model is scored exactly as the reader meets it in the app."""
import re

TASHKEEL = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")   # same set as ArabicText.TASHKEEL (escaped: RTL text reorders when typed)
MARKS = re.compile(r"[ً-ْ]")                                           # real vowel marks, for "has tashkeel"
NONLETTER = re.compile(r"[^ء-ي٠-٩A-Za-z0-9\s]")
CLAUSE = re.compile(r"[.!?؟;؛،,:\n]+")
END = re.compile(r"[.!?؟]+[»\"')\]]*\s*$")

def strip(t): return TASHKEEL.sub("", t)
def norm(t): return re.sub(r"\s+", " ", strip(t)).strip()
def words(t): return NONLETTER.sub(" ", strip(t)).split()
def longest_clause(t): return max([len(words(c)) for c in CLAUSE.split(t)] or [0])

AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
def numbers(t): return sorted(re.findall(r"\d+(?:[.,]\d+)?", t.translate(AR_DIGITS)))

NEG = re.compile(r"(?:^|\s)[وف]?(لا|لم|لن|ليس|ليست|ليسوا|لست|غير|دون|بدون|بلا)(?=\s|$)")
def negations(t): return len(NEG.findall(norm(t)))

PROBES = {   # A2 "hard spots": what a sentence contains that a careless rewrite tends to break
    "negation": NEG,
    "number": re.compile(r"\d|[٠-٩]|(?:^|\s)[وب]?(واحد|اثن|ثلاث|أربع|خمس|ست|سبع|ثمان|تسع|عشر|مئة|مائة|ألف|مليون)"),
    "condition": re.compile(r"(?:^|\s)[وف]?(لو|إن|إذا|لولا|كلما|متى|مهما)(?=\s)"),
    "cause": re.compile(r"(?:^|\s)[وف]?(لأن|لأنه|لأنها|بسبب|إذ|لذلك|لذا|بما أن|نتيجة)(?=\s)"),
    "quantity": re.compile(r"(?:^|\s)[وف]?(كل|بعض|جميع|معظم|أغلب|شتى|فقط|إلا|سوى|أكثر|أقل)(?=\s)"),
    "certainty": re.compile(r"(?:^|\s)[وف]?(قد|ربما|يجب|لعل|يمكن|ينبغي|لابد|لا بد|يجوز|يحتمل)(?=\s)"),
}
def probes(t): return [k for k, p in PROBES.items() if p.search(norm(t))]

def end_mark(t):
    m = END.search(t.strip())
    return re.sub(r"[»\"')\]\s]", "", m.group(0))[-1:] if m else ""

# ---- house punctuation rules (grammar_ref/CHECKLIST.md), checked without the judge ----
def rule_breaks(source, output):
    """House rules the output breaks that the source did not already break."""
    return [r for r in _breaks(source, output) if r not in _breaks(source, source)]

def _breaks(source, output):
    """Names of the house rules the output breaks. Only rules that a regex can check without false alarms."""
    out, br = output.strip(), []
    src_inner = re.search(r"[.!?؟]\s+\S", source.strip()[:-1] if source.strip() else "")
    if not src_inner and re.search(r"(?<![.\d\s])\.(?!\.)\s+\S", out[:-1]):
        # a full stop inside the output where the source had none, except after a one-letter abbreviation
        for m in re.finditer(r"(\S+)\.(?!\.)\s+\S", out[:-1]):
            if len(strip(m.group(1))) > 1 and not m.group(1)[-1].isdigit(): br.append("mid-sentence full stop"); break
    if MARKS.search(out): br.append("tashkeel")
    if re.search(r"،\s*(لأن|إذ)\s", norm(out)): br.append("، before لأن/إذ (needs ؛)")
    if re.search(r"(?:^|\s)[و]?لو\s[^.؟!]*?،\s*ف\S", norm(out)) and not re.search(r"(?:^|\s)[و]?لو\s[^.؟!]*?،\s*ف\S", norm(source)):
        br.append("ف after لو")
    if re.search(r"،\s*و(يكون|كان|فعل|يحدث) ذلك", norm(out)) and not re.search(r"،\s*و(يكون|كان|فعل|يحدث) ذلك", norm(source)):
        br.append("filler join")
    return br

# ---- the app, in Python ----
SENTENCE_END = re.compile(r"(?<=[.!?؟])\s+(?=\S)")
INNER_STOP = re.compile(r"(?<![.\d])\.(?!\.)(\s+)(?=\S)")
CAUSE = re.compile(r"^(لأن|لأنه|لأنها|لأنهم|لأني|لأننا|إذ)")
CLITICS = ["وال", "بال", "كال", "فال", "لل", "ال", "و", "ف", "ب", "ل"]
MIN_WORDS, MIN_RETENTION = 6, 0.35

def paragraphs(text):
    out = []
    for p in re.split(r"\n\s*\n|\n", text.strip()):
        s = [x.strip() for x in SENTENCE_END.split(re.sub(r"[ \t ]+", " ", p.strip())) if x.strip()]
        if s: out.append(s)
    return out

def _nw(w):
    w = re.sub(r"[^\w]", "", strip(w)).replace("إ", "ا").replace("أ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    for c in CLITICS:
        if w.startswith(c) and len(w) - len(c) >= 3: return w[len(c):]
    return w

def retention(source, output):
    src = [w for w in map(_nw, source.split(" ")) if len(w) >= 3]
    if not src: return 1.0
    out = set(map(_nw, output.split(" ")))
    return sum(w in out for w in src) / len(src)

def fix_punctuation(source, output):
    if re.search(r"[.!?؟]\s", source.rstrip()[:-1]): return output
    res, last = [], 0
    for m in INNER_STOP.finditer(output):
        before = output[:m.start()].rstrip().rsplit(" ", 1)[-1]
        if len(before) == 1: continue
        rest = output[m.end():]
        res.append(output[last:m.start()] + ("؛" if CAUSE.search(rest) else "،") + m.group(1)); last = m.end()
    return "".join(res) + output[last:]

def pieces(selection):
    """The pieces the app sends to the model, in order: (paragraph index, sentence, goes to model?)."""
    return [(p, s, len([w for w in s.replace("\n", " ").split(" ") if w.strip()]) >= MIN_WORDS)
            for p, ss in enumerate(paragraphs(strip(selection))) for s in ss]

def assemble(selection, outputs, guards):
    """Join per-piece model outputs the way Simplifier does. guards=False gives the raw model: same splitting and
    short-piece pass-through, but no retention fallback and no punctuation fix."""
    res, prev, it = "", None, iter(outputs)
    for p, s, to_model in pieces(selection):
        if prev is not None: res += "\n\n" if p != prev else " "
        prev = p
        out = next(it) if to_model else s
        if guards and to_model:
            out = s if (not out.strip() or retention(s, out) < MIN_RETENTION) else fix_punctuation(s, out)
        res += out
    return res

import hashlib
def key(source, output):
    """Judge-cache key of a (selection, output) pair."""
    return hashlib.sha1((norm(source) + "\x00" + norm(output)).encode()).hexdigest()[:16]

# ---- the full-stop variant: the same output with the clause joins the model added written as full stops ----
import difflib
_TOK = re.compile(r"،|[^\s،]+")
# a clause that can stand alone after the comma: opens with a connective (the only start we can spot without a parser;
# asyndetic clauses stay commas, so the variant under-splits rather than over-splits)
CLAUSE_START = re.compile(r"^(و|ف)(?!ي$|ى$)\S{2,}|^(ثم|لكن|ولكن|لذلك|لذا|بل)$")
def comma_to_stops(source, output):
    """Replace every «،» the output added (not aligned to a «،» in the source) with a full stop. Measurement only: the
    product keeps «،» joins; this asks what the easier-text measures say when splits are written the way split-and-
    rephrase corpora write them (separate sentences). Only commas that open a new clause (see CLAUSE_START) with 3+
    words on each side are converted; appositions and lists keep their commas."""
    a = [norm(t) for t in _TOK.findall(source)]
    bt = _TOK.findall(output); b = [norm(t) for t in bt]
    new = set()
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if tag != "equal": new |= {j for j in range(j1, j2) if bt[j] == "،"}
    def piece(j, step):             # words from j up to the next clause mark, going forward or back
        n = 0
        while 0 <= j < len(bt) and bt[j] != "،" and not re.search(r"[.!?؟؛:]$", bt[j] if step > 0 else bt[j] + "x"):
            n += 1; j += step
        return n
    out = ""
    for j, t in enumerate(bt):
        stop = (t == "،" and j in new and j + 1 < len(bt) and CLAUSE_START.match(strip(bt[j + 1]))
                and piece(j + 1, 1) >= 3 and piece(j - 1, -1) >= 3)
        if t == "،": out += "." if stop else "،"
        else: out += (" " if out else "") + t
    return out
