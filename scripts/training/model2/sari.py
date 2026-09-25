"""Faithful port of the SARI implementation HuggingFace `evaluate` wraps
(Xu et al. 2016 / EASSE), so the numbers are comparable to model 1's reported
SARI. Validated by reproducing model 1's full-dev figure (77.06) exactly."""
import re
import sys
from collections import Counter

import pandas as pd


def normalize(sentence):
    """sacrebleu 13a-style: separate punctuation, collapse whitespace."""
    s = sentence.strip()
    s = re.sub(r"([\{-\~\[-\` -\&\(-\+\:-\@\/])", r" \1 ", s)
    s = re.sub(r"([^0-9])([\.,])", r"\1 \2 ", s)
    s = re.sub(r"([\.,])([^0-9])", r" \1 \2", s)
    s = re.sub(r"([0-9])(-)", r"\1 \2 ", s)
    return re.sub(r"\s+", " ", s).strip()


def ngrams(tokens, n):
    return [" ".join(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def sari_ngram(sgrams, cgrams, rgramslist, numref):
    rgramcounter = Counter([g for rg in rgramslist for g in rg])
    sgramcounter_rep = Counter({g: c * numref for g, c in Counter(sgrams).items()})
    cgramcounter_rep = Counter({g: c * numref for g, c in Counter(cgrams).items()})

    # KEEP
    keep_rep = sgramcounter_rep & cgramcounter_rep
    keep_good = keep_rep & rgramcounter
    keep_all = sgramcounter_rep & rgramcounter
    t1 = sum(keep_good[g] / keep_rep[g] for g in keep_good)
    t2 = sum(keep_good.values())
    kp = t1 / len(keep_rep) if len(keep_rep) > 0 else 1
    kr = t2 / sum(keep_all.values()) if sum(keep_all.values()) > 0 else 1
    keepscore = 2 * kp * kr / (kp + kr) if (kp + kr) > 0 else 0

    # DELETE (precision only, as in the reference implementation)
    del_rep = sgramcounter_rep - cgramcounter_rep
    del_good = del_rep - rgramcounter
    d1 = sum(del_good[g] / del_rep[g] for g in del_good)
    dp = d1 / len(del_rep) if len(del_rep) > 0 else 1

    # ADD
    add_all_c = set(Counter(cgrams)) - set(Counter(sgrams))
    add_good = add_all_c & set(rgramcounter)
    add_all_r = set(rgramcounter) - set(Counter(sgrams))
    ap = len(add_good) / len(add_all_c) if len(add_all_c) > 0 else 1
    ar = len(add_good) / len(add_all_r) if len(add_all_r) > 0 else 1
    addscore = 2 * ap * ar / (ap + ar) if (ap + ar) > 0 else 0

    return keepscore, dp, addscore


def sari_sentence(source, prediction, references):
    s = normalize(source).split()
    c = normalize(prediction).split()
    rs = [normalize(r).split() for r in references]
    numref = len(rs)
    keep, dele, add = [], [], []
    for n in range(1, 5):
        k, d, a = sari_ngram(ngrams(s, n), ngrams(c, n), [ngrams(r, n) for r in rs], numref)
        keep.append(k); dele.append(d); add.append(a)
    return 100 * (sum(keep) / 4 + sum(dele) / 4 + sum(add) / 4) / 3


def corpus_sari(df):
    return sum(sari_sentence(r.original_text, r.prediction, [r.reference])
               for r in df.itertuples()) / len(df)


if __name__ == "__main__":
    df = pd.read_csv(sys.argv[1])
    for col in ("original_text", "reference", "prediction"):
        df[col] = df[col].fillna("").astype(str).str.strip()

    changed = df[df.reference != df.original_text]
    unchanged = df[df.reference == df.original_text]
    words = df.original_text.str.split().str.len()
    real = df[words >= 5]
    real_changed = real[real.reference != real.original_text]

    print(f"{'bucket':<34}{'n':>7}{'SARI':>9}")
    for name, sub in (
        ("FULL DEV (Ahmed's number)", df),
        ("  changed references", changed),
        ("  unchanged references", unchanged),
        ("sentences >=5 words", real),
        ("  >=5 words AND changed", real_changed),
    ):
        print(f"{name:<34}{len(sub):>7}{corpus_sari(sub):>9.2f}")
