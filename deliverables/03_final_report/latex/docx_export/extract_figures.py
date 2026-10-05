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


def crop_above_caption(page: fitz.Page, caption_rect: fitz.Rect, pad_top=8) -> fitz.Rect:
    """Region from the figure body above the caption (TikZ drawings / images / labels)."""
    cap_top = caption_rect.y0
    # generous fallback — TikZ diagrams can be very tall
    best_top = cap_top - 380
    for img in page.get_image_info():
        r = fitz.Rect(img["bbox"])
        if r.y1 <= cap_top + 2 and r.y0 < cap_top:
            best_top = min(best_top, r.y0)
    try:
        for d in page.get_drawings():
            r = d["rect"]
            if r.y1 <= cap_top + 6 and r.height > 4 and r.y0 < cap_top:
                best_top = min(best_top, r.y0)
    except Exception:
        pass
    # chart labels / nodes: any short text block above the caption
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = b
        if y1 <= cap_top + 2 and y0 < cap_top and (cap_top - y1) < 420:
            if len(text) < 400 and (y1 - y0) < 120:
                best_top = min(best_top, y0)
    # stop at the previous long prose paragraph or previous caption
    for b in page.get_text("blocks"):
        x0, y0, x1, y1, text, *_ = b
        if y1 <= best_top + 2 and y0 < best_top:
            if len(text) > 350 or (y1 - y0) > 50:
                # leave a little gap under that prose
                best_top = max(best_top, y1 + 4)
    best_top = max(best_top, 36)
    width = page.rect.width
    left, right = 36, width - 36
    return fitz.Rect(left, best_top - pad_top, right, cap_top - 2)


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
