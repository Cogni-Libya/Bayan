#!/bin/sh
# Score every model-2 system on BayanBench v2 (dev and test) with the bench's own CLI, and the paired effects.
# Meaning kept = P(same) >= 0.5 (frozen from the human ratings) and every number kept.
#   BENCH_SRC=<bayanbench/src> DATA=<bayanbench-data snapshot> PREDS=<preds dir> PY=<python with torch> sh run.sh
set -e
cd "$(dirname "$0")"
EXTRA=""
for f in scores/*.jsonl; do [ -f "$f" ] && EXTRA="$EXTRA --meaning-scores $f"; done
score() { PYTHONPATH="$BENCH_SRC" "$PY" -m bayanbench.cli score "$@" --data "$DATA" --meaning-threshold 0.5 $EXTRA; }
for split in dev test; do
  for s in copy model2-arat5 model2-arabart model2-arat5-notag model2-arabart-notag app-arat5 app-arabart; do
    score "$PREDS/$split/$s.jsonl" --split $split --json "$split.$s.json" > "$split.$s.txt"
  done
  # paired effects: one change at a time (b against its baseline a)
  for pair in "model2-arat5 model2-arat5-notag" "model2-arabart model2-arabart-notag" \
              "model2-arat5-notag app-arat5" "model2-arabart-notag app-arabart" \
              "app-arabart app-arat5" "model2-arabart model2-arat5" "model2-arabart-notag model2-arat5-notag"; do
    set -- $pair
    score "$PREDS/$split/$2.jsonl" --baseline "$PREDS/$split/$1.jsonl" --split $split --json "$split.$2-vs-$1.json" > "$split.$2-vs-$1.txt"
  done
done
echo done
