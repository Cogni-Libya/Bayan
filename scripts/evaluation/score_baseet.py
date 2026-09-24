#!/usr/bin/env python3
"""
Score a model on Baseet's test split with Baseet's own scorer, so our numbers sit directly beside
the Baseet paper's. Tashkeel is stripped from everything (tatweel is kept).

    uv run --with "easse @ git+https://github.com/feralvam/easse.git@6a4352ec299ed03fda8ee45445ca43d9c7673e89" \
        python scripts/evaluation/score_baseet.py --test baseet_test.csv \
        --pred-L3 pred_baseet_L3.jsonl --pred-L2 pred_baseet_L2.jsonl --pred-L1 pred_baseet_L1.jsonl

baseet_test.csv: Original_Sentence, ref_level_1..3, pred_level_1..3 (Baseet's own model), in_samer.
Prediction ids are the row numbers of that file. Each level is scored against its own reference,
on all rows and on the rows whose source is not in SAMER (the fairer comparison, since SAMER
sentences are in our training data but not in Baseet's).
Prints one table: our model, the copy baseline, and Baseet's published model.
"""

import argparse
import json
import re

import pandas as pd
from easse.sari import corpus_sari

DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")


def strip(s) -> str:
    return DIAC.sub("", str(s))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--test", required=True)
    for lv in (3, 2, 1):
        p.add_argument(f"--pred-L{lv}", required=True)
    args = p.parse_args()

    t = pd.read_csv(args.test)
    preds = {}
    for lv in (3, 2, 1):
        with open(getattr(args, f"pred_L{lv}"), encoding="utf-8") as f:
            rows = {int(json.loads(l)["id"]): json.loads(l)["prediction"] for l in f if l.strip()}
        assert len(rows) == len(t), f"L{lv}: {len(rows)} predictions for {len(t)} test rows"
        preds[lv] = rows

    print(f"{'subset':14}{'level':>6}{'n':>6}{'ours':>8}{'copy':>8}{'Baseet':>8}")
    for name, mask in (("all", [True] * len(t)), ("not_in_samer", (~t.in_samer).tolist())):
        idx = [i for i, m in enumerate(mask) if m]
        src = [strip(t.Original_Sentence[i]) for i in idx]
        for lv in (3, 2, 1):
            refs = [[strip(t[f"ref_level_{lv}"][i]) for i in idx]]
            ours = [strip(preds[lv][i]) if str(preds[lv][i]).strip() else src[k] for k, i in enumerate(idx)]
            baseet = [strip(t[f"pred_level_{lv}"][i]) for i in idx]
            s = lambda sys_: corpus_sari(orig_sents=src, sys_sents=sys_, refs_sents=refs)
            print(f"{name:14}{'L' + str(lv):>6}{len(idx):>6}{s(ours):8.2f}{s(src):8.2f}{s(baseet):8.2f}")


if __name__ == "__main__":
    main()
