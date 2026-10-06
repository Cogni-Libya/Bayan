#!/usr/bin/env bash
# Render the scenes whose inputs changed to out/media/videos/scenes/1000p30/*.mp4 (1444x1000, 30 fps).
# Usage: ./render_videos.sh [--force] [Scene ...]   (see render_changed.py for what counts as changed)
cd "$(dirname "$0")"
exec python3 render_changed.py "$@"
