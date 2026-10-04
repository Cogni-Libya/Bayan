"""How easy a text is to read, measured without a judge.

- Reading level: CAMeL Lab's BAREC readability model (CAMeL-Lab/readability-arabertv02-word-CE, 19 levels, public),
  run per sentence; we keep the hardest sentence's level, and the hardest clause's (split at ، ؛ too), because the
  house style joins split clauses with «،» and the model, trained on whole sentences, reads them as one sentence.
  Needs the [ease] extra (torch, transformers). Levels are cached by text in ~/.cache/bayanbench/ease.jsonl.
- Hard words: SAMER word levels 4-5 (word familiarity is the best-supported aid for dyslexic readers). SAMER's licence
  forbids redistributing it, so the lexicon is built from YOUR licensed copy of the SAMER corpus
  (--samer <folder with data/train.analyzed.tsv>) and cached locally. Without it, the hard-word measures are
  reported as not measured."""
import collections
import csv
import hashlib
import json
import os
import re
from pathlib import Path

from .text import _nw, norm, strip

MODEL = "CAMeL-Lab/readability-arabertv02-word-CE"
CACHE = Path(os.environ.get("BAYANBENCH_CACHE", Path.home() / ".cache" / "bayanbench"))
NONLETTER = re.compile(r"[^ء-ي\s]")
SENT = re.compile(r"[.!?؟;؛\n]+")
CLAUSE_SPLIT = re.compile(r"[.!?؟;؛،,\n]+")


def ar_words(t):
    return NONLETTER.sub(" ", strip(t)).split()


def sentences(t):
    return [s.strip() for s in SENT.split(strip(t)) if ar_words(s)]


def clauses(t):
    return [c.strip() for c in CLAUSE_SPLIT.split(strip(t)) if ar_words(c)]


def tkey(t):
    return hashlib.sha1(norm(t).encode()).hexdigest()[:16]


# ---- hard words (SAMER, local only) ----
def samer_lexicon(samer_dir):
    """({form: level}, {clitic-stripped form: level}): the most common SAMER level each form was annotated with."""
    CACHE.mkdir(parents=True, exist_ok=True)
    f1, f2 = CACHE / "samer_lex.json", CACHE / "samer_lex_stripped.json"
    if f1.exists() and f2.exists():
        return json.loads(f1.read_text(encoding="utf-8")), json.loads(f2.read_text(encoding="utf-8"))
    if not samer_dir:
        return None
    tsv = Path(samer_dir) / "data" / "train.analyzed.tsv"
    if not tsv.exists():
        raise SystemExit(f"--samer: {tsv} not found (point it at the samer-simplification-corpus-v1 folder)")
    csv.field_size_limit(2 ** 31 - 1)
    lv = collections.defaultdict(collections.Counter)
    with open(tsv, encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f, delimiter="\t"):
            for col in ("L5", "L4", "L3"):
                for m in re.finditer(r"#([٠-٥0-5])#(\S+)", r[col]):
                    for w in ar_words(m.group(2)):
                        lv[w][int(m.group(1).translate(str.maketrans("٠١٢٣٤٥", "012345")))] += 1
    stripped = collections.defaultdict(collections.Counter)
    for w, c in lv.items():
        stripped[_nw(w)].update(c)
    lex, slex = ({w: c.most_common(1)[0][0] for w, c in d.items()} for d in (lv, stripped))
    f1.write_text(json.dumps(lex, ensure_ascii=False), encoding="utf-8")
    f2.write_text(json.dumps(slex, ensure_ascii=False), encoding="utf-8")
    return lex, slex


def hard_words(t, lex):
    """Words SAMER puts at level 4 or 5. Words SAMER never annotated are not counted either way."""
    lx, sx = lex
    return sum(1 for w in ar_words(t) if (lx.get(w, sx.get(_nw(w))) or 0) >= 4)


# ---- reading level (CAMeL readability model) ----
class Levels:
    """{text key: {"level_max", "clause_level_max"}} for every text asked for; measures what the cache lacks."""

    def __init__(self, seed=None):
        CACHE.mkdir(parents=True, exist_ok=True)
        self.path = CACHE / "ease.jsonl"
        self.known = {}
        for p in [seed, self.path]:
            if p and Path(p).exists():
                with open(p, encoding="utf-8") as f:
                    for line in f:
                        r = json.loads(line)
                        self.known[r["key"]] = r

    def measure(self, texts, device=None, log=print):
        todo = {tkey(t): t for t in texts if tkey(t) not in self.known}
        if not todo:
            return
        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer
        except ImportError:
            raise SystemExit("reading level needs the [ease] extra: pip install 'bayanbench[ease]' (or use --no-level)")
        log(f"reading level: {len(todo)} new texts")
        tok = AutoTokenizer.from_pretrained(MODEL)
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        model = AutoModelForSequenceClassification.from_pretrained(MODEL).to(dev).eval()
        segs = sorted({s for t in todo.values() for s in sentences(t) + clauses(t)})
        level = {}
        with torch.no_grad():
            for i in range(0, len(segs), 64):
                b = segs[i:i + 64]
                enc = tok(b, return_tensors="pt", padding=True, truncation=True, max_length=256).to(dev)
                for s, y in zip(b, model(**enc).logits.argmax(-1).tolist()):
                    level[s] = y + 1
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            for k, t in todo.items():
                r = {"key": k, "level_max": max([level[s] for s in sentences(t)] or [0]),
                     "clause_level_max": max([level[c] for c in clauses(t)] or [0])}
                self.known[k] = r
                f.write(json.dumps(r) + "\n")

    def get(self, t):
        return self.known.get(tkey(t))
