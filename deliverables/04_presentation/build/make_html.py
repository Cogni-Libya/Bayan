"""Presenting deck as ONE self-contained HTML file, with no reveal.js.

    python make_html.py [--auto] [Scene ...]  -> ../Bayan_Presenting.html

Reads slides/<Scene>.json (written by manim-slides when scenes render) and embeds every step video.
Exactly one step video is visible at a time (the others are display:none), so steps cannot draw over each
other. Every step plays once and holds on its last frame until you click. With --auto, steps flagged
auto_next (manim-slides) play straight into the next one instead.

Keys: Right / Space / click / PageDown = next step, Left / PageUp = previous, Home = start, F = fullscreen.
"""
import base64
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE.parent / "Bayan_Presenting.html"
SCENES = "S1Cover S2Problem S3Data SPipeline S4Models S5Measure S6Results S7Phone S8Close S9End".split()

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bayan — pitch</title>
<style>
  html, body { margin: 0; height: 100%; overflow: hidden; background: #000; }
  #stage { position: fixed; inset: 0; transition: none; }
  video { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: contain; display: none; }
  video.on { display: block; }
  #count { position: fixed; right: 8px; bottom: 6px; font: 12px/1 system-ui, sans-serif; color: #888; opacity: .6; pointer-events: none; }
</style>
</head>
<body>
<div id="stage"></div>
<div id="count"></div>
<script>
const STEPS = __STEPS__;   // [{scene, bg, auto, b64}]
const stage = document.getElementById("stage"), count = document.getElementById("count");
const vids = STEPS.map((s) => {
  const bytes = Uint8Array.from(atob(s.b64), (c) => c.charCodeAt(0));
  const v = document.createElement("video");
  v.src = URL.createObjectURL(new Blob([bytes], { type: "video/mp4" }));
  v.muted = true; v.playsInline = true; v.preload = "auto";
  stage.appendChild(v);
  return v;
});
let cur = -1;
function show(i) {
  i = Math.max(0, Math.min(STEPS.length - 1, i));
  if (cur >= 0) { vids[cur].pause(); vids[cur].classList.remove("on"); }
  cur = i;
  const v = vids[i];
  v.currentTime = 0;
  v.classList.add("on");
  document.body.style.background = stage.style.background = STEPS[i].bg;
  count.textContent = (i + 1) + " / " + STEPS.length;
  v.play().catch(() => {});
}
vids.forEach((v, i) => v.addEventListener("ended", () => { if (i === cur && STEPS[i].auto && i < STEPS.length - 1) show(i + 1); }));
const next = () => show(cur + 1), prev = () => show(cur - 1);
addEventListener("keydown", (e) => {
  if (["ArrowRight", "ArrowDown", " ", "PageDown", "Enter"].includes(e.key)) { e.preventDefault(); next(); }
  else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(e.key)) { e.preventDefault(); prev(); }
  else if (e.key === "Home") show(0);
  else if (e.key === "f" || e.key === "F") document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
});
addEventListener("click", next);
show(0);
</script>
</body>
</html>
"""


def main():
    steps = []
    auto = "--auto" in sys.argv
    for scene in [a for a in sys.argv[1:] if not a.startswith("--")] or SCENES:
        data = json.loads((HERE / "slides" / f"{scene}.json").read_text())
        for st in data["slides"]:
            steps.append({
                "scene": scene,
                "bg": data["background_color"],
                "auto": auto and bool(st["auto_next"]),
                "b64": base64.b64encode((HERE / (st.get("src") or st["file"])).read_bytes()).decode(),
            })
    OUT.write_text(PAGE.replace("__STEPS__", json.dumps(steps)))
    print(f"{OUT.name}: {len(steps)} steps, {OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
