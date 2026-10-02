# Manim → PPTX spike (2026-09-29)

Venvs: `.venv-slides` (manim 0.21 + manim-slides), `.venv-pptx` (manim 0.18.1 + manim-pptx). Scenes in `spike/`.

| | manim-slides (`manim-slides convert --to=pptx`) | manim-pptx (RythenGlyth) |
|---|---|---|
| Works out of the box | Yes, on manim 0.21 | No: needs `constants.FFMPEG_BIN = "ffmpeg"` shim and manim <= 0.18 |
| Output | 1 MP4 per `next_slide()`, poster = first frame, 16:9 | 1+ MP4 per `endSlide()`, 16:9 |
| Uses the SIC template | No (blank 16:9 deck) | No |

Neither tool knows the SIC template (4:3-ish, 9902825 x 6858000 EMU), so the final deck is assembled with python-pptx
onto the template's layouts, embedding the per-slide MP4s (+ poster PNGs) ourselves.

## Arabic in manim (important)
- `Text("كتب")` returns ZERO glyphs for any single Arabic word (any font, with or without diacritics, trailing space or
  punctuation too). Two or more words, or Arabic next to Latin, render fine. Silent: no error.
- `MarkupText(...)` renders single words correctly. Use it for every Arabic string.
- `Text(..., disable_ligatures=True)` raises ValueError on Arabic.
- Shaping and diacritics are correct in Amiri, Noto Naskh Arabic, Noto Sans Arabic.
- `background_color` needs `ManimColor("#...")`, not a string, in manim 0.21.
- `arrange(RIGHT)` puts the first item on the LEFT; use `arrange(LEFT)` for Arabic reading order.

## Samsung logo
The SAMSUNG wordmark in the template is a vector freeform (layouts 2, 9, 10), not an image. Extracted to
`assets/samsung-{blue,white,ink}.svg` (path from the template, viewBox 2179x334). `assets/sic-slogan-white.png` is the
"Together for Tomorrow! Enabling People" slogan (white, transparent).
