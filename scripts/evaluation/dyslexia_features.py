#!/usr/bin/env python3
"""
Dyslexia-oriented measures of model outputs against their inputs. Numbers only; no references needed.

    uv run python scripts/evaluation/dyslexia_features.py --barec-train data/raw/barec/train.csv \
        pred_barec_samer.jsonl pred_barec_L3.jsonl pred_barec_L2.jsonl pred_barec_L1.jsonl

Each prediction file holds {"id", "source", "prediction"} per line. For each file it prints the
source value -> the output value of:
  words/sent  words per sentence (sentences split on . ! ? ؟ ; ؛ and line breaks)
  rare %      words outside the 5,000 most frequent forms in BAREC train
  long %      words of 7+ letters
  ambig %     words a reader can misread without tashkeel: the bare form has 2+ conflicting readings in
              BAREC's tashkeel, each seen 3+ times and in 10%+ of the word's vowelled occurrences.
              BAREC's tashkeel is partial, so a spelling with fewer marks (هذِه) is merged into the full
              reading it fits (هَذِهِ), not counted as a new reading; the case ending is ignored
and three row counts:
  split %     outputs with more sentences than their source
  copy %      outputs identical to their source (ignoring tashkeel and punctuation)
  lost        outputs shorter than half their source, in words: our count of lost content

Lexicons come from BAREC train only, never from a test split. Tashkeel is stripped before measuring.
"""

import argparse
import collections
import csv
import json
import re
import statistics as st
from pathlib import Path

DIAC = re.compile(r"[ؐ-ًؚ-ٰٟ]")
NON_LETTER = re.compile(r"[^ء-ي\s]")
SENT = re.compile(r"[.!?؟;؛\n]+")


def words(text: str) -> list[str]:
    return NON_LETTER.sub(" ", DIAC.sub("", str(text))).split()


VOWELS = set("\u064B\u064C\u064D\u064E\u064F\u0650")   # tanween, fatha, damma, kasra (sukun is optional in writing)
SHADDA = "\u0651"


def marks(token: str) -> list[list]:
    """Per letter: [vowel or None, shadda, annotated]. A letter the annotator left bare fits any reading."""
    out = []
    for ch in token:
        if "\u0621" <= ch <= "\u064A":
            out.append([None, False, False])
        elif out and DIAC.match(ch):
            out[-1][2] = True
            if ch in VOWELS:
                out[-1][0] = ch
            elif ch == SHADDA:
                out[-1][1] = True
    if out:
        out[-1][0] = None        # the last letter's vowel is the case ending: grammar, not a different word
    return out


def conflict(a: list, b: list) -> bool:
    """Two spellings are different readings only where both are marked and the marks disagree."""
    return any((va and vb and va != vb) or (ka and kb and sa != sb)
               for (va, sa, ka), (vb, sb, kb) in zip(a, b))


def is_ambiguous(spellings: collections.Counter, min_count: int = 3, min_share: float = 0.10) -> bool:
    """Merge partial spellings into the readings they fit; ambiguous if 2+ readings are each well attested."""
    total = sum(spellings.values())
    readings = []                                                    # [members, count]
    for tok, n in spellings.most_common():
        m = marks(tok)
        for r in readings:
            if not any(conflict(m, x) for x in r[0]):
                r[0].append(m)
                r[1] += n
                break
        else:
            readings.append([[m], n])
    return sum(n >= min_count and n / total >= min_share for _, n in readings) >= 2


def lexicons(barec_train: Path) -> tuple[set, set]:
    with open(barec_train, encoding="utf-8-sig", newline="") as f:
        sents = [row["Sentence"] for row in csv.DictReader(f)]
    freq = collections.Counter(w for s in sents for w in words(s))
    top = {w for w, _ in freq.most_common(5000)}
    spellings = collections.defaultdict(collections.Counter)
    for s in sents:
        if not DIAC.search(s):
            continue
        for tok in re.sub(r"[^\u0621-\u064A\u064B-\u0652\u0670\s]", " ", s).split():
            if DIAC.search(tok):
                spellings[DIAC.sub("", tok)][tok] += 1
    return top, {w for w, c in spellings.items() if is_ambiguous(c)}


def feats(text: str, top: set, ambig: set) -> dict | None:
    w = words(text)
    if not w:
        return None
    n_sents = max(1, len([x for x in SENT.split(DIAC.sub("", str(text))) if words(x)]))
    n = len(w)
    return {"words": n / n_sents, "sents": n_sents, "n": n,
            "rare": sum(x not in top for x in w) / n,
            "long": sum(len(x) >= 7 for x in w) / n,
            "ambig": sum(x in ambig for x in w) / n}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--barec-train", required=True, type=Path)
    p.add_argument("predictions", nargs="+", type=Path)
    args = p.parse_args()
    top, ambig = lexicons(args.barec_train)

    print(f"{'file':28}{'rows':>6}{'words/sent':>14}{'rare %':>14}{'long %':>14}{'ambig %':>14}"
          f"{'split %':>9}{'copy %':>8}{'lost':>6}")
    for path in args.predictions:
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        pairs = [(feats(r["source"], top, ambig), feats(r["prediction"], top, ambig)) for r in rows]
        pairs = [(a, b) for a, b in pairs if a and b]
        m = lambda k, i, scale=1: scale * st.mean(pair[i][k] for pair in pairs)
        cell = lambda k, scale: f"{m(k, 0, scale):6.1f}→{m(k, 1, scale):<6.1f}"
        split = 100 * sum(b["sents"] > a["sents"] for a, b in pairs) / len(pairs)
        copy = 100 * sum(words(r["source"]) == words(r["prediction"]) for r in rows) / len(rows)
        lost = sum(len(words(r["prediction"])) < 0.5 * len(words(r["source"])) for r in rows)
        print(f"{path.name:28}{len(rows):>6}{cell('words', 1):>14}{cell('rare', 100):>14}{cell('long', 100):>14}"
              f"{cell('ambig', 100):>14}{split:9.1f}{copy:8.1f}{lost:6d}")


if __name__ == "__main__":
    main()
