"""Wrap the phone recording in an Android bezel on the deck's beige.

    python build_bezel.py  -> assets/demo_bezel.mp4 + assets/demo_bezel-poster.jpg

Canvas is the render canvas (1444x1000). The phone is ~80% of the slide height, centered, with rounded
corners and a soft drop shadow. The recording plays under a PIL-drawn overlay whose
screen area is transparent with rounded corners, so the video needs no mask of its own.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).parent
ASSETS = HERE / "assets"
W, H = 1444, 1000
PAPER = (0xF6, 0xF2, 0xE6)
BODY = (0x1B, 0x1A, 0x17)
PHONE_H = 800
BEZEL = 14
ASPECT = 1080 / 2316  # the recording's aspect ratio


def main():
    sh = PHONE_H - 2 * BEZEL
    sw = round(sh * ASPECT) // 2 * 2
    pw = sw + 2 * BEZEL
    x0, y0 = (W - pw) // 2, (H - PHONE_H) // 2
    sx, sy = x0 + BEZEL, y0 + BEZEL

    shadow = Image.new("L", (W, H), 0)
    ImageDraw.Draw(shadow).rounded_rectangle((x0, y0 + 18, x0 + pw, y0 + PHONE_H + 18), 52, fill=110)
    shadow = shadow.filter(ImageFilter.GaussianBlur(26))

    S = 4  # supersample the overlay for smooth corners
    ov = Image.new("RGBA", (W * S, H * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    d.rounded_rectangle((x0 * S, y0 * S, (x0 + pw) * S, (y0 + PHONE_H) * S), 52 * S, fill=BODY + (255,))
    hole = Image.new("L", ov.size, 0)
    ImageDraw.Draw(hole).rounded_rectangle((sx * S, sy * S, (sx + sw) * S, (sy + sh) * S), 40 * S, fill=255)
    alpha = ov.getchannel("A")
    alpha.paste(0, mask=hole)
    ov.putalpha(alpha)
    ov = ov.resize((W, H), Image.LANCZOS)

    base = Image.new("RGB", (W, H), PAPER)
    base.paste(Image.new("RGB", (W, H), (60, 45, 25)), mask=shadow.point(lambda a: a * 0.55))
    overlay_png = HERE / "out" / "bezel_overlay.png"
    base_png = HERE / "out" / "bezel_base.png"
    overlay_png.parent.mkdir(exist_ok=True)
    ov.save(overlay_png)
    base.save(base_png)

    out = ASSETS / "demo_bezel.mp4"
    fc = f"[1:v]scale={sw}:{sh}[v];[0:v][v]overlay={sx}:{sy}[b];[b][2:v]overlay=0:0,format=yuv420p[o]"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-framerate", "30", "-i", str(base_png),
                    "-i", str(ASSETS / "demo.mp4"), "-i", str(overlay_png), "-filter_complex", fc,
                    "-map", "[o]", "-map", "1:a?", "-shortest", "-r", "30", "-c:v", "libx264", "-crf", "18",
                    "-c:a", "aac", "-movflags", "+faststart", str(out)], check=True)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(out), "-vframes", "1", "-q:v", "2",
                    str(ASSETS / "demo_bezel-poster.jpg")], check=True)
    print(f"{out.name}: phone {pw}x{PHONE_H} ({PHONE_H / H:.0%} of slide height), screen {sw}x{sh}")


if __name__ == "__main__":
    main()
