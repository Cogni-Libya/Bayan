#!/usr/bin/env bash
# Layout check: render the last frame of every scene (or the named ones) to out/media/images
cd "$(dirname "$0")"
for s in ${@:-S1Cover S2Problem S3Gap S4Verdict S5Data S6Candidates S7Model1 S8Model2 S9Close}; do
  .venv-slides/bin/manim render -s --resolution 1444,1000 --media_dir out/media scenes.py $s 2>&1 | grep -E "^[A-Za-z]*Error|scenes.py:" | head -3
done
