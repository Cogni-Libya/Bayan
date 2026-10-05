# Pitch deck build (4 minutes, two speakers)

Two decks from the same story and the same numbers. Every figure comes from `facts.py` and is
verified by `check_numbers.py` before rendering.

| | Presenting (Manim + HTML) | Submission (`../Bayan_Submission.pptx`) |
|---|---|---|
| Made of | Manim scenes played live or exported to a self-contained HTML file | Native PowerPoint shapes and text, PowerPoint's own animations |
| Beats | 8 scenes (cover, problem, data, models, measuring, results, phone, close) | **still the 5 Oct 7-slide content; needs a rebuild to the 8 scenes** |
| Editable | No (re-render) | Yes |
| Fonts | baked into the video | must be installed: Readex Pro, Noto Naskh Arabic, Amiri |
| Source | `scenes.py`, `common.py` | `nativekit.py`, `build_native.py` |

## Build

```bash
# numbers check — must pass before anything is rendered
.venv-slides/bin/python check_numbers.py

# presenting deck: render scenes (~1 min each, 1444x1000 @ 30 fps)
./render_videos.sh [Scene..]

# live player (Qt window)
manim-slides present S1Cover S2Problem S3Data S4Models S5Measure S6Results S7Phone S8Close

# portable HTML export (single file, no install needed; one click per step)
python make_html.py

# submission deck (seconds) -- NOT yet updated to the 8 scenes
.venv-slides/bin/python build_native.py

# presenter script
.venv-slides/bin/python make_script.py
```

## How the beats work

- HTML player (`make_html.py`): every step plays once and waits for a click. `--auto` honours the
  `auto_next` flags instead (steps flow on; each beat stops at its end), as `manim-slides present` does.
- `common.Deck` provides `begin_beat()`, `step()` (auto-advance) and `hold()` (pause point).
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
- Demo video placeholder is in `S7Phone`. Recording checklist is in the presenter script.
