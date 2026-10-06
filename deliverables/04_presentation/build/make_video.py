"""Presenting deck as ONE mp4 video of the whole presentation.

    python make_video.py [--hold 3.5] [Scene ...]  -> ../Bayan_Presenting.mp4

Reads slides/<Scene>.json (written by manim-slides when scenes render) exactly like make_html.py and
cuts the step videos into one mp4: every step plays once, steps flagged auto_next (manim-slides) flow
straight into the next one, and a beat that stops (auto_next False) freezes its last frame for --hold
seconds. Each step is normalized to the render canvas (1444x1000, 30 fps) with object-fit: contain
semantics: fit the step video inside the canvas and pad with the scene background color.
"""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "Bayan_Presenting.mp4"
SCENES = "S1Cover S2Problem S3Data S4Models SPipeline S5Measure S6Results S7Phone S8Close S9End".split()
FPS = 30
SEG = HERE / "out" / "video_segments"


def run(*cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"FAILED: {' '.join(cmd[:2])}...\n{r.stderr[-800:]}")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    hold = 3.5
    for i, a in enumerate(sys.argv):
        if a == "--hold":
            hold = float(sys.argv[i + 1])
    steps = []
    for scene in args or SCENES:
        data = json.loads((HERE / "slides" / f"{scene}.json").read_text())
        for st in data["slides"]:
            steps.append((scene, data["background_color"], data["resolution"], st))

    SEG.mkdir(parents=True, exist_ok=True)
    for old in SEG.glob("*.mp4"):
        old.unlink()

    segs = []
    for i, (scene, bg, (w, h), st) in enumerate(steps):
        src = HERE / st["file"]
        if st.get("src") and (HERE / st["src"]).exists():
            src = HERE / st["src"]  # external clip (the phone demo): play the source itself
        stop = 0.0 if st["auto_next"] else hold
        if i == len(steps) - 1:
            stop = max(stop, 2 * hold)  # tail so the deck does not cut away instantly
        vf = (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
              f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=0x{bg.lstrip('#')},"
              f"fps={FPS},setsar=1")
        if stop > 0:
            vf += f",tpad=stop_mode=clone:stop_duration={stop}"
        vf += ",format=yuv420p"
        seg = SEG / f"{i:02d}_{scene}.mp4"
        run("ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf,
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an", str(seg))
        segs.append(seg)
        print(f"{i:02d} {scene:<9} {'STOP ' + format(stop, 'g') + 's' if stop else 'flow':<10} {src.name}")

    listing = SEG / "concat.txt"
    listing.write_text("".join(f"file '{s.resolve()}'\n" for s in segs))
    run("ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c", "copy", "-movflags", "+faststart", str(OUT))
    print(f"{OUT.name}: {len(steps)} steps, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
