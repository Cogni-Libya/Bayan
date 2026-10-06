"""PRESENTING deck: SIC template + Manim videos, one PowerPoint slide per click step.

    python assemble_presenting.py  -> ../Bayan_Presenting.pptx  and  ../Bayan_Presenting_static.pdf

Each scene is cut into steps with self.next_slide(); manim-slides writes one MP4 per step (slides/<Scene>.json).
Every step is a full-bleed autoplaying video on its own slide, starting on the previous step's last frame, so a
click looks like the same animation continuing. Poster frame = the step's last frame. Steps of one scene are
grouped into a PowerPoint section. Speaker notes sit on each scene's first step.
"""
import json
import subprocess
import uuid
from pathlib import Path

from lxml import etree
from PIL import Image
from script_data import slide_notes, step_notes
from pptx import Presentation
from pptx.util import Emu

HERE = Path(__file__).parent
DECK_DIR = HERE.parent
TEMPLATE = next(DECK_DIR.glob("SIC_AI_Capstone*Template.pptx"))
SLIDES_DIR = HERE / "slides"
OUT = DECK_DIR / "Bayan_Presenting.pptx"
PDF = DECK_DIR / "Bayan_Presenting_static.pdf"

SLIDES = [  # (scene, alt text, notes: None = taken from script_data)
    ("S1Cover", "Cover: Bayan, simplify Arabic where you read, on the phone, offline. Team Cogni, Samsung Innovation Campus", None),
    ("S2Problem", "11% of Arab primary-school children have developmental dyslexia; the word كتب has three readings; shorter clauses help, and Bayan's scope", None),
    ("S3Data", "Corpus v1 pipeline: BAREC, strip tashkeel, route, Gemma 4 31B, code, readability and meaning gates, 14,975 rows", None),
    ("SPipeline", "The pipeline: source corpora, leakage check, meaning gate at 0.85, fine-tune, BayanBench v2; the loop carries the v0.1, v0.2 and v0.3 findings back into the data", None),
    ("S4Models", "Three model lanes: model 1 (SAMER), model 2 (more data and tags), model 3 (corpus v1); dropped branches", None),
    ("S5Measure", "BayanBench: copy trap, three kinds of measure, the scorer checked against six raters (AUC 0.85), one reader with dyslexia", None),
    ("S6Results", "Trade-off scatter; model 3 minus the shipped large model with intervals: simplifies more, keeps less meaning, copies more", None),
    ("S7Phone", "Phone recording slot; what the app does; AraBART default 222 MB and AraT5v2 optional 471 MB on a Xiaomi Mi 11X", None),
    ("S8Close", "Simplify where you read. Limits: no reader has used Bayan, scorer stricter than people, simplifying more costs meaning", None),
]

# Same mechanism manim-slides uses: a root-level video node with delay 0 starts playback when the slide appears.
TIMING = (
    '<p:timing xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"><p:tnLst><p:par>'
    '<p:cTn id="1" dur="indefinite" restart="never" nodeType="tmRoot"><p:childTnLst><p:video>'
    '<p:cMediaNode vol="80000"><p:cTn id="2" fill="hold" display="0"><p:stCondLst><p:cond delay="0"/></p:stCondLst></p:cTn>'
    '<p:tgtEl><p:spTgt spid="{spid}"/></p:tgtEl></p:cMediaNode></p:video></p:childTnLst></p:cTn></p:par></p:tnLst></p:timing>'
)


def last_frame(mp4: Path, png: Path):
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-sseof", "-0.05", "-i", str(mp4), "-vframes", "1", str(png)], check=True)
    if not png.exists():  # -sseof can seek past the last packet on short clips and write nothing
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(mp4), "-vframes", "1", str(png)], check=True)


P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"


def add_sections(prs, groups):
    """groups: [(name, [slide index, ...])] -> PowerPoint sections so the slide sorter shows one group per slide."""
    ids = [s.get("id") for s in prs.slides._sldIdLst]
    pres = prs.part._element
    ns = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main"}
    ext_lst = pres.find("p:extLst", ns)
    if ext_lst is None:
        ext_lst = etree.SubElement(pres, "{%s}extLst" % ns["p"])
    for ext in ext_lst.findall("p:ext", ns):
        if ext.get("uri") == "{521415D9-36F7-43E2-AB2F-B90AF26B5E84}":
            ext_lst.remove(ext)
    ext = etree.SubElement(ext_lst, "{%s}ext" % ns["p"], uri="{521415D9-36F7-43E2-AB2F-B90AF26B5E84}")
    sec_lst = etree.SubElement(ext, "{%s}sectionLst" % P14, nsmap={"p14": P14})
    for n, (name, idxs) in enumerate(groups):
        sec = etree.SubElement(sec_lst, "{%s}section" % P14, name=name, id="{%s}" % uuid.uuid5(uuid.NAMESPACE_URL, f"bayan-{n}"))
        lst = etree.SubElement(sec, "{%s}sldIdLst" % P14)
        for i in idxs:
            etree.SubElement(lst, "{%s}sldId" % P14, id=ids[i])


def main():
    prs = Presentation(TEMPLATE)
    ids = prs.slides._sldIdLst
    for sld in list(ids):  # drop the four sample slides but keep master, layouts and theme
        prs.part.drop_rel(sld.rId)
        ids.remove(sld)
    layout = next(l for l in prs.slide_layouts if l.name == "Body")
    cx, cy = prs.slide_width, prs.slide_height
    tmp = HERE / "out/posters"
    tmp.mkdir(parents=True, exist_ok=True)

    pages, groups, n = [], [], 0
    for scene, alt, notes in SLIDES:
        steps = json.loads((SLIDES_DIR / f"{scene}.json").read_text())["slides"]
        idxs = []
        for k, step in enumerate(steps, 1):
            mp4 = HERE / step["file"]
            png = tmp / f"{scene}_{k}.png"
            last_frame(mp4, png)
            slide = prs.slides.add_slide(layout)
            for ph in list(slide.placeholders):
                ph._element.getparent().remove(ph._element)
            movie = slide.shapes.add_movie(str(mp4), 0, 0, cx, cy, poster_frame_image=str(png), mime_type="video/mp4")
            movie._element.nvPicPr.cNvPr.set("descr", f"{alt} (step {k} of {len(steps)})")
            movie.name = f"{scene} step {k} (Manim video)"
            slide._element.append(etree.fromstring(TIMING.format(spid=movie.shape_id)))
            slide.notes_slide.notes_text_frame.text = step_notes(scene, k)
            pages.append(Image.open(png).convert("RGB"))
            idxs.append(n)
            n += 1
        groups.append((f"{len(groups) + 1}. {scene[2:]}", idxs))

    add_sections(prs, groups)
    prs.save(OUT)
    pages[0].save(PDF, save_all=True, append_images=pages[1:], resolution=150)
    print(f"{OUT.name}: {n} slides in {len(SLIDES)} sections, {OUT.stat().st_size / 1e6:.1f} MB; {PDF.name}")


if __name__ == "__main__":
    main()
