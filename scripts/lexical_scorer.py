"""Word-level lexical difficulty for Arabic text: LLM age-of-acquisition (AoA) ratings plus corpus frequency.

AoA table: data/processed/word_aoa/word_aoa_llm.parquet, rated by rate_words_llm.py and built by build_word_aoa_table.py
(DeepSeek ratings, 1 = learned earliest ... 7 = latest; validated against the Kalimah human norms, Spearman +0.71, and against SAMER's human word
levels, +0.62). Words missing from the table get an AoA imputed from their frequency, using a quadratic fit of AoA on
Zipf frequency over the rated vocabulary (skipping unrated words instead drops the hard, rare ones and hurts).

Frequency: `wordfreq` Arabic Zipf frequency, best reading over clitic-stripped stems, unknown = 1.0 (very rare).
Pure Python + wordfreq + polars; no CAMeL Tools. Surface forms are matched through the rated table directly, then
clitic-stripped stems, then the BAREC surface->lemma map if data/processed/barec_surface_to_lemma.parquet exists.

    from lexical_scorer import LexicalScorer
    ls = LexicalScorer()
    mean_aoa, mean_zipf, n_words = ls.text(arabic_text)      # lower AoA / higher Zipf = easier
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import polars as pl
from wordfreq import zipf_frequency

PROJECT_ROOT = Path(__file__).resolve().parent.parent
AOA_PATH = PROJECT_ROOT / "data" / "processed" / "word_aoa" / "word_aoa_llm.parquet"
S2L_PATH = PROJECT_ROOT / "data" / "processed" / "barec_surface_to_lemma.parquet"

DIAC = re.compile("[ً-ْٰـ]")
TOKEN = re.compile("[ء-يٱ-ۓً-ْٰـ]+")
PRE = ["و", "ف", "ب", "ل", "ك", "س", "ال", "وال", "فال", "بال", "لل", "كال", "ولل", "وب", "ول", "وس", "فس", "فب", "فل"]
SUF = ["ه", "ها", "هم", "هن", "ك", "كم", "نا", "ني", "ي", "ة", "ات", "ون", "ين", "ان", "ا"]


def normalize(tok: str) -> str:
    """Strip diacritics and tatweel; drop a leading definite article (the rated table's key format)."""
    tok = DIAC.sub("", tok)
    return tok[2:] if tok.startswith("ال") and len(tok) > 3 else tok


def stems(tok: str) -> list[str]:
    """Plausible clitic-stripped stems of a surface token, longest first."""
    out = {tok}
    for p in [""] + PRE:
        if p and not tok.startswith(p):
            continue
        base = tok[len(p):]
        for s in [""] + SUF:
            st = base[:len(base) - len(s)] if s and base.endswith(s) else (base if not s else None)
            if st and len(st) >= 2:
                out.add(st)
    return sorted(out, key=len, reverse=True)


class LexicalScorer:
    def __init__(self, aoa_path: Path = AOA_PATH, s2l_path: Path = S2L_PATH):
        if not aoa_path.exists():
            raise FileNotFoundError(f"{aoa_path} not found; create it with rate_words_llm.py, then build_word_aoa_table.py")
        t = pl.read_parquet(aoa_path)
        self.aoa = dict(zip(t["word"].to_list(), t["aoa_llm"].to_list()))
        self.s2l = {}
        if s2l_path.exists():
            m = pl.read_parquet(s2l_path)
            self.s2l = dict(zip(m["surface"].to_list(), m["lemma"].to_list()))
        z = np.array([max(zipf_frequency(w, "ar"), 1.0) for w in self.aoa])
        self.coef = np.polyfit(z, np.array(list(self.aoa.values())), 2)
        self._zipf: dict[str, float] = {}
        self._aoa: dict[str, float] = {}

    def zipf(self, tok: str) -> float:
        if tok not in self._zipf:
            c = DIAC.sub("", tok)
            z = max((zipf_frequency(s, "ar") for s in stems(c)), default=0.0)
            self._zipf[tok] = z if z > 0 else 1.0
        return self._zipf[tok]

    def rated(self, tok: str) -> float | None:
        c = normalize(tok)
        if c in self.aoa:
            return self.aoa[c]
        for s in stems(c):
            if normalize(s) in self.aoa:
                return self.aoa[normalize(s)]
        lemma = self.s2l.get(DIAC.sub("", tok))
        return self.aoa.get(normalize(lemma)) if lemma else None

    def aoa_of(self, tok: str) -> float:
        if tok not in self._aoa:
            a = self.rated(tok)
            self._aoa[tok] = a if a is not None else float(np.clip(np.polyval(self.coef, self.zipf(tok)), 1, 7))
        return self._aoa[tok]

    def text(self, text: str) -> tuple[float, float, int]:
        """(mean AoA, mean Zipf, number of Arabic words); NaN, NaN, 0 when the text has none."""
        toks = TOKEN.findall(text)
        if not toks:
            return float("nan"), float("nan"), 0
        return (float(np.mean([self.aoa_of(t) for t in toks])), float(np.mean([self.zipf(t) for t in toks])), len(toks))
