"""The BAREC `Word` text variant: the input format CAMeL Lab's readability models were trained on.

The models (CAMeL-Lab/readability-*-word-CE) expect diacritics removed, characters cleaned and punctuation split
into separate tokens, NOT raw text; raw text collapses on diacritized input. `to_word` reproduces that variant.

It is a self-contained reduction of four CAMeL Tools functions (MIT, Copyright 2018-2026 New York University
Abu Dhabi): dediac_ar, normalize_unicode, CharMapper("arclean") and simple_word_tokenize. They are vendored so that
nobody has to install CAMeL Tools, whose dependencies (torch, scipy, pandas, a compiled kenlm, ...) are far heavier
than these four small functions. The character map is third_party/camel_tools/arclean_map.json, unchanged, with
the licence next to it.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

_MAP_PATH = Path(__file__).resolve().parent / "third_party" / "camel_tools" / "arclean_map.json"

_DIACRITICS = re.compile("[ً-ْٰ]")
_UNICODE_FIX = {"﷼": "ريال", "﷽": "بسم الله الرحمن الرحيم"}  # applied before NFKC, as in normalize_unicode
_YEH_INITIAL = re.compile(r"(^|(?<=\s))ی")
# Characters BAREC's Word variant keeps although `arclean` would rewrite or delete them.
_KEEP = frozenset("؟؛•﴿﴾٠١٢٣٤٥٦٧٨٩")


def _load_arclean() -> tuple[dict[str, str | None], str]:
    spec = json.loads(_MAP_PATH.read_text(encoding="utf-8"))
    table: dict[str, str | None] = {}
    for key, value in spec["charMap"].items():  # a single character or "a-z"; later entries override earlier ones
        first, last = (key, key) if len(key) == 1 else (key[0], key[2])
        for code in range(ord(first), ord(last) + 1):
            table[chr(code)] = value
    return table, spec["default"]  # None keeps the character; characters missing from the map get `default` ("": deleted)


_ARCLEAN, _ARCLEAN_DEFAULT = _load_arclean()


def _clean(char: str) -> str:
    mapped = _ARCLEAN.get(char, _ARCLEAN_DEFAULT)
    return char if mapped is None else mapped


def _tokenize(text: str) -> list[str]:
    """Split on whitespace and give every punctuation or symbol character its own token."""
    tokens: list[str] = []
    for word in text.split():
        start = 0
        for i, char in enumerate(word):
            if unicodedata.category(char)[0] in "PS":
                if i > start:
                    tokens.append(word[start:i])
                tokens.append(char)
                start = i + 1
        if start < len(word):
            tokens.append(word[start:])
    return tokens


def to_word(text: str) -> str:
    text = _DIACRITICS.sub("", text)
    text = unicodedata.normalize("NFKC", "".join(_UNICODE_FIX.get(c, c) for c in text))
    text = _YEH_INITIAL.sub("ى", text).replace("ی", "ي")  # Persian yeh: word-initial -> alef maksura, elsewhere -> yeh
    return " ".join(_tokenize("".join(c if c in _KEEP else _clean(c) for c in text)))
