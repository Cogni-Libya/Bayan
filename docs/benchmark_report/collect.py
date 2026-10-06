"""Official BayanBench v2.0 scorecards for every system in systems.py, dev and test, paired against today's app.

  BAYANBENCH_DATA=<snapshot> SAMER_DIR=<licensed SAMER> python collect.py [--only KEY ...]

Writes build/scores/{split}__{key}.json (skipped when it already exists). Needs the bayanbench package (v2.0) and its
[ease] extra. Thresholds: the frozen v2.0 rule (meaning kept = P(same) >= 0.5 and every number kept); the joint rate
uses --simpler-min 2,0.5 (2 clause words or half a level), our own analysis setting, labelled as such in the report.
"""
import argparse, subprocess, sys
from pathlib import Path

import systems as S

HERE = Path(__file__).resolve().parent
OUT = HERE / "build" / "scores"
BASE = "app-arat5"

ap = argparse.ArgumentParser()
ap.add_argument("--only", nargs="*")
ap.add_argument("--split", nargs="*", default=["dev", "test"])
a = ap.parse_args()
OUT.mkdir(parents=True, exist_ok=True)
ms = [x for f in S.meaning_files() for x in ("--meaning-scores", str(f))]
for split in a.split:
    outs = S.outputs(split)
    for key, preds in outs.items():
        if a.only and key not in a.only:
            continue
        j = OUT / f"{split}__{key}.json"
        if j.exists():
            continue
        cmd = [sys.executable, "-m", "bayanbench.cli", "score", str(preds), "--data", str(S.BENCH), "--split", split,
               "--joint", "--simpler-min", "2,0.5", "--json", str(j)] + ms
        cmd += ["--samer", S.SAMER] if S.SAMER else ["--no-samer"]
        if key != BASE:
            cmd += ["--baseline", str(outs[BASE])]
        r = subprocess.run(cmd, capture_output=True, text=True)
        (OUT / f"{split}__{key}.txt").write_text(r.stdout + r.stderr, encoding="utf-8")
        print(split, key, "ok" if r.returncode == 0 and j.exists() else f"FAILED ({r.returncode})", flush=True)
