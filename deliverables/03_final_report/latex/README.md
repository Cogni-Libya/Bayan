# Bayan final report — LaTeX source

Builds with **tectonic** alone; no TeX Live installation, no `biber`, no
`bibtex`. Tectonic fetches the packages it needs on first run.

```sh
tectonic -X compile main.tex        # -> main.pdf
```

| File | What it holds |
|---|---|
| `main.tex` | the report: sections, prose, tables, inline bibliography |
| `bayan.sty` | house style — SIC palette, blue section banners, cover, evidence labels |
| `figures.tex` | the five figures (TikZ diagrams and pgfplots charts) |
| `refs.bib` | the same references in BibTeX form, for reuse elsewhere |

## Notes

**Fonts.** SamsungOne is not redistributable and is not installed here, so
Liberation Sans stands in for it; both are humanist sans faces at similar
widths. Swap `\setmainfont` in `bayan.sty` on a machine that has SamsungOne.
Arabic is set in PakType Naskh Basic — Noto's Arabic faces are *variable*
fonts, which XeTeX cannot load.

**Bibliography.** Carried inline as `thebibliography` so the document builds
with tectonic alone. `refs.bib` holds the same entries for anyone who wants
them; several are marked `VERIFY` and must be checked against the published
record before submission.

**Evidence labels.** `\measured`, `\decided` and `\planned` mark every claim.
The label is part of the argument, not decoration — see the Action Plan for
the same convention.
