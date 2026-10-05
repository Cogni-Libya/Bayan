#!/usr/bin/env python3
"""Crop figure regions and cover page out of Bayan_Final_Report.pdf."""
from __future__ import annotations

import sys
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
PDF = HERE.parent.parent / "Bayan_Final_Report.pdf"
OUT_FIGS = HERE / "figs"
OUT_FIGS.mkdir(exist_ok=True)

# Caption label -> logical name. Cropped region is everything above the caption
# that sits in the same figure block (tracked via Figure/Table labels).
FIGURE_NAMES = {
    1: "fig01_schedule",
    2: "fig02_evolution",
    3: "fig03_pipeline",
    4: "fig04_architecture",
    5: "fig05_cleaning",
    6: "fig06_lengths",
    7: "fig07_sari",
    8: "fig08_behaviour",
    9: "fig09_trainingtwo",
    10: "fig10_scorer",
    11: "fig11_tradeoff",
    12: "fig12_ui",
}


def find_text_pages(doc: fitz.Document, needle: str):
    hits = []
    for i, page in enumerate(doc):
        rects = page.search_for(needle)
        if rects:
            hits.append((i, rects))
    return hits


def crop_above_caption(page: fitz.Page, caption_rect: fitz.Rect, pad=6) -> fitz.Rect:
    """Graphics-only region directly above the caption.

    Walk upward from the caption through drawings/images that touch the growing
    band; stop at the first body-text block (prose, previous caption, table rows,
    heading). Text is only kept when it sits inside the graphics band (axis and
    node labels), so surrounding prose never ends up inside the PNG.
    """
    cap_top = caption_rect.y0
    rects = [fitz.Rect(i["bbox"]) for i in page.get_image_info()]
    rects += [d["rect"] for d in page.get_drawings()]
    rects = [r for r in rects if r.y1 <= cap_top + 2 and r.height > 0.5]

    # nearest body-text block above the caption = hard ceiling. Short text
    # (labels) is ignored here; anything long or multi-line counts as prose.
    ceiling = 36.0
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if y1 > cap_top - 1:
            continue
        inside = any(r.y0 - 2 <= y0 and y1 <= r.y1 + 2 for r in rects)
        if not inside and (len(text) > 80 or y1 - y0 > 24):
            ceiling = max(ceiling, y1)

    # grow upward through graphics below the ceiling, allowing small gaps
    top = cap_top
    for r in sorted((r for r in rects if r.y0 >= ceiling - 1), key=lambda r: -r.y1):
        if r.y1 >= top - 30:
            top = min(top, r.y0)
    # labels hugging the graphics (panel titles, axis names) above that top
    for x0, y0, x1, y1, text, *_ in page.get_text("blocks"):
        if ceiling <= y0 and y1 <= top + 2 and top - y1 < 20 and len(text) <= 80:
            top = min(top, y0)
    left, right = 36, page.rect.width - 36
    return fitz.Rect(left, max(top - pad, ceiling + 1), right, cap_top - 2)


def main():
    doc = fitz.open(PDF)
    print(f"pages={doc.page_count}")

    # Cover page 1
    page0 = doc[0]
    pix = page0.get_pixmap(dpi=200)
    cover = HERE / "cover1.png"
    pix.save(cover)
    print("wrote", cover.name, pix.width, pix.height)

    # Locate every "Figure N." caption
    found = 0
    for n, name in FIGURE_NAMES.items():
        needle = f"Figure {n}."
        hits = find_text_pages(doc, needle)
        # Prefer the caption that starts a figure caption (search may hit body)
        chosen = None
        for pno, rects in hits:
            for r in rects:
                # caption is near bottom half of figure; accept first on page
                chosen = (pno, r)
                break
            if chosen:
                break
        if not chosen:
            print(f"MISS Figure {n}.")
            continue
        pno, cap_rect = chosen
        page = doc[pno]
        crop = crop_above_caption(page, cap_rect)
        # Expand left/right slightly to banner-ish content width
        pix = page.get_pixmap(clip=crop, dpi=250)
        out = OUT_FIGS / f"{name}.png"
        pix.save(out)
        found += 1
        print(f"Figure {n:2d} page={pno+1:2d} crop=({crop.x0:.0f},{crop.y0:.0f})-({crop.x1:.0f},{crop.y1:.0f}) -> {out.name} {pix.width}x{pix.height}")

    print(f"extracted {found}/{len(FIGURE_NAMES)} figures")


if __name__ == "__main__":
    sys.exit(main())
