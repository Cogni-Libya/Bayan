"""Render only the scenes whose inputs changed (render_videos.sh calls this).

    python render_changed.py [--force] [Scene ...]

A scene's fingerprint is its class source in scenes.py plus everything every scene shares (common.py,
facts.py, the manim version, the assets folder, build_bezel.py). The fingerprint is stored in
out/stamps/<Scene>.hash after a successful render; a scene is skipped when its stamp matches and its
slides/<Scene>.json still exists. Editing one Deck class re-renders that scene only; touching a shared
file re-renders all of them.
"""
import ast
import hashlib
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
SCENES = "S1Cover S2Problem S3Data S4Models SPipeline S5Measure S6Results S7Phone S8Close S9End".split()
STAMPS = HERE / "out" / "stamps"
SHARED = ["common.py", "facts.py", "build_bezel.py", "uv.lock"]


def shared_hash():
    h = hashlib.sha256()
    for f in SHARED:
        h.update((HERE / f).read_bytes())
    for p in sorted((HERE / "assets").rglob("*")):
        if p.is_file():
            h.update(p.name.encode() + p.read_bytes() if p.stat().st_size < 2e6
                     else f"{p.name}{p.stat().st_size}{int(p.stat().st_mtime)}".encode())
    return h.hexdigest()


def scene_sources():
    src = (HERE / "scenes.py").read_text()
    tree = ast.parse(src)
    lines = src.splitlines()
    top = "\n".join(ast.get_source_segment(src, n) or "" for n in tree.body if not isinstance(n, ast.ClassDef))
    return top, {n.name: "\n".join(lines[n.lineno - 1:n.end_lineno]) for n in tree.body if isinstance(n, ast.ClassDef)}


def main():
    force = "--force" in sys.argv
    wanted = [a for a in sys.argv[1:] if not a.startswith("--")] or SCENES
    shared = shared_hash()
    top, classes = scene_sources()
    STAMPS.mkdir(parents=True, exist_ok=True)
    for s in wanted:
        fp = hashlib.sha256((shared + top + classes[s]).encode()).hexdigest()
        stamp = STAMPS / f"{s}.hash"
        if not force and stamp.exists() and stamp.read_text() == fp and (HERE / "slides" / f"{s}.json").exists():
            print(f"== {s}: unchanged, skipped")
            continue
        print(f"== {s}")
        stamp.unlink(missing_ok=True)
        r = subprocess.run(["uv", "run", "manim", "render", "--resolution", "1444,1000", "--fps", "30",
                            "--media_dir", "out/media", "scenes.py", s], cwd=HERE, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"{s} failed:\n{(r.stdout + r.stderr)[-800:]}")
        stamp.write_text(fp)
    print("DONE")


if __name__ == "__main__":
    main()
