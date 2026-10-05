#!/usr/bin/env bash
# Render every scene to out/media/videos/scenes/1000p30/*.mp4 at the template's aspect ratio (1444x1000, 30 fps)
cd "$(dirname "$0")"
for s in ${@:-S1Cover S2Problem S3Data S4Models S5Measure S6Results S7Phone S8Close}; do
  echo "== $s"; uv run manim render --resolution 1444,1000 --fps 30 --media_dir out/media scenes.py $s 2>&1 | grep -E "^[A-Za-z]*Error|scenes.py:|File ready" | head -3
done
echo DONE
