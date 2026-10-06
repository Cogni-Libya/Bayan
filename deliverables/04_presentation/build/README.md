# Pitch deck build (4 minutes, one speaker)

Two decks from the same story and the same numbers. Every figure comes from `facts.py` and is
verified by `check_numbers.py` before rendering.

| | Presenting (Manim + HTML) | Submission (`../Bayan_Submission.pptx`) |
|---|---|---|
| Made of | Manim scenes played live or exported to a self-contained HTML file | Native PowerPoint shapes and text, PowerPoint's own animations |
| Beats | 10 scenes (cover, problem, data, pipeline, models, measuring, results, phone, close, end card) | 22 slides — one per presenting step, so a static render matches the HTML click-through |
| Editable | No (re-render) | Yes |
| Fonts | baked into the video | must be installed: Readex Pro, Noto Naskh Arabic, Amiri |
| Source | `scenes.py`, `common.py` | `nativekit.py`, `build_native.py` |

## Regenerate from scratch

Clone the repo, then from `deliverables/04_presentation/build/` (this folder is its own `uv`
project — `pyproject.toml` + `uv.lock` live here and nowhere else):

```bash
# 0. install the deck toolchain (Python ≥ 3.12)
uv sync

# fonts (already under fonts/ReadexPro.ttf; also install on the system for Manim/Pango)
#   Noto Naskh Arabic and Amiri — used for on-slide Arabic
cp fonts/ReadexPro.ttf ~/.local/share/fonts/ && fc-cache -f

# 1. numbers check — must pass before anything is rendered
uv run python check_numbers.py

# 2. presenting deck: render scenes (~1 min each, 1444x1000 @ 30 fps)
./render_videos.sh

# 3. live player (Qt window)
uv run manim-slides present S1Cover S2Problem S3Data S4Models SPipeline S5Measure S6Results S7Phone S8Close

# 4. portable HTML export (single file, no install needed; one click per step)
uv run python make_html.py            # -> ../Bayan_Presenting.html
uv run python make_html.py --auto     # same, steps flow on within a beat

# 5. submission deck (seconds, no Manim)
uv run python build_native.py         # -> ../Bayan_Submission.pptx

# 6. presenter script (same SPEECH text as both decks' speaker notes)
uv run python make_script.py          # -> ../Bayan_Presenter_Script.md
```

Step 2 is the only slow one. `render_videos.sh` writes `out/media/videos/scenes/1000p30/*.mp4`
and `slides/<Scene>.json`; both are gitignored regenerable intermediates. `make_html.py` embeds
those MP4s as base64, so the HTML file travels alone. `build_native.py` needs only `python-pptx`
and the assets under `assets/` and the SIC template in the parent folder.

If you only changed the submission deck (`build_native.py` / `nativekit.py`), steps 1 and 5 are enough.
If you only changed wording (`script_data.py`), run 1, 5 and 6 (and re-render if the wording is
on-slide in `scenes.py`).

## How the beats work

- HTML player (`make_html.py`): every step plays once and waits for a click. `--auto` honours the
  `auto_next` flags instead (steps flow on; each beat stops at its end), as `manim-slides present` does.
- `common.Deck` provides `begin_beat()`, `step()` (auto-advance) and `hold()` (pause point).
- The native deck keeps the same speaker notes as the presenting scenes. Each presenting step is
  its own PowerPoint slide (no build-up animations), so the deck also reads correctly in a PDF
  export, in Google Slides and on paper.
- Numbers are spoken as words; تبسيط is said *tabseet*.

## Number policy

- Every on-slide figure is in `facts.py` with a `src` field naming its origin.
- `check_numbers.py` resolves each `src` (file path or PR) and fails if it is missing.
- Sources starting `git:` are checked against the final report in git (`origin/docs/final-report-draft`); `peer:` figures come from a teammate's session and print UNVERIFIED.
- It also scans `scenes.py`, `build_native.py` and `script_data.py` for superseded claims
  (Baseet, 22733, 250 MB, 77.5 SARI, etc.) and refuses to let them into the deck.
- Run it before rendering. It must say "all numbers sourced" with 0 failures.

## Notes

- Manim: Arabic must go through `A()` (MarkupText); plain `Text` drops single Arabic words
  (`SPIKE_NOTES.md`).
- Native: animations are hand-written PresentationML (`nativekit.build_timing`). Open in real
  PowerPoint, never LibreOffice.
- Text floor is 11 pt at slide size (`common.MIN_SIZE`).
- Demo video placeholder is in `S7Phone` / native slide 7. Recording checklist is in the
  presenter script. When `../05_demo/bayan_demo.mp4` exists, pass it to `step(src=...)` in
  `S7Phone` and call `Canvas.add_movie()` on native slide 6.
- `Bayan_Presenting.pptx` is obsolete (LibreOffice flashes black between video slides). Use the
  HTML player or `manim-slides present`.
