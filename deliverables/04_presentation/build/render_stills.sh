#!/usr/bin/env bash
# Layout check: render the last frame of every scene (or the named ones) to out/media/images
cd "$(dirname "$0")"
for s in ${@:-S1Cover S2Problem S3Data S4Models S5Measure S6Results S7Phone S8Close S9End}; do
  uv run manim render -s --resolution 1444,1000 --media_dir out/media scenes.py $s 2>&1 | grep -E "^[A-Za-z]*Error|scenes.py:" | head -3
done
