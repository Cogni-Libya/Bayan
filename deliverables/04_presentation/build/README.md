# Pitch deck build (idea → verdict → data → training)

Two decks from the same story and the same numbers (checked: only slide numbers, the live 11% counter and a hex colour differ).

| | Presenting (`../Bayan_Presenting.pptx`) | Submission (`../Bayan_Submission.pptx`) |
|---|---|---|
| Made of | Manim videos, one autoplaying video per click step | Native PowerPoint shapes and text, PowerPoint's own animations |
| Slides | 24 (9 sections, one per scene) | 9, several clicks each |
| Editable | No (re-render) | Yes |
| Fonts | baked into the video | must be installed: Readex Pro, Noto Naskh Arabic, Amiri |
| Source | `scenes.py`, `common.py`, `assemble_presenting.py` | `nativekit.py`, `build_native.py` |

```bash
uv venv --python 3.12 .venv-slides && uv pip install --python .venv-slides/bin/python manim manim-slides python-pptx pillow
# presenting deck (renders ~1 min per scene, 1444x1000 @ 30 fps)
./render_videos.sh [Scene..] && .venv-slides/bin/python assemble_presenting.py
manim-slides present S1Cover S2Problem S3Gap S4Verdict S5Data S6Candidates S7Model1 S8Model2 S9Close   # live player, same steps
# submission deck (seconds)
.venv-slides/bin/python build_native.py
```

- Manim: Arabic must go through `A()` (MarkupText); plain `Text` drops single Arabic words (`SPIKE_NOTES.md`).
- Native: animations are hand-written PresentationML (`nativekit.build_timing`). Checked by: every target shape exists, ids
  unique, LibreOffice parses the intended click structure. NOT played in real PowerPoint: click through it once.
- Native slide 7 shows both charts side by side, so it reads correctly where animations are ignored (PDF, previews).
- Text in the Manim deck is small for a room (smallest about 8 pt at slide size); the native deck uses >= 10.5 pt.
- Every number comes from `Bayan_Final_Report.pdf` (28 Sep 2026); speaker notes are in `assemble_presenting.py` (`SLIDES`).
