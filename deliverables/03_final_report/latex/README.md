# Bayan final report — LaTeX source

The SIC AI Capstone **Final Report template**, rebuilt in LaTeX: the template's
own cover page, its fonts (SamsungOne, Samsung Sharp Sans), its A4 margins,
blue section banners, "Content" page, grid tables with the pale-blue header row,
the team-review and instructor-score tables, and the `Page N / M` footer. Every
measurement is taken from the template's `document.xml`; see the header of
`bayan.sty`.

## Build

```sh
# once: pull the fonts and the cover page out of the template
python extract_template_assets.py "path/to/SIC_AI_Capstone Project_Final Report.docx"

# whenever the evaluation is re-run: regenerate every reported number
python make_results.py eval
# and the BayanBench tables, from the private bench folder
python make_bench_results.py ~/MyProjects/Bayan/data/processed/bench

tectonic -X compile main.tex        # -> main.pdf
```

Builds with **tectonic** alone (no TeX Live, no biber). Without `fonts/` the
report falls back to Liberation Sans; `fonts/` is gitignored because Samsung's
fonts are not ours to publish.

| File | What it holds |
|---|---|
| `main.tex` | the report, in the template's six sections, plus an abstract, related work, BayanBench, limitations and ethics |
| `bayan.sty` | the template's layout and styles |
| `figures.tex` | timeline, architecture, workflow, EDA, training and UI figures (TikZ/pgfplots) |
| `results.tex` | **generated** by `make_results.py` — test-set tables, SARI and behaviour charts, and every number quoted from them |
| `bench_results.tex` | **generated** by `make_bench_results.py` — model 2 on BayanBench (code tier, test and dev, item sets, paired effects) |
| `make_bench_results.py` | reads the bench's items, model outputs and reading-level cache; computes every measure with the bench's own `lib.py`/`ease.py`, with document-bootstrap intervals |
| `make_results.py` | reads `score.py` outputs and behaviour statistics, writes `results.tex` |
| `extract_template_assets.py` | de-obfuscates the template's embedded fonts; renders its cover page to `assets/sic_cover.pdf` |
| `eval/` | the numbers behind `results.tex`: `score.py` outputs, behaviour statistics, and the scripts that produced them (no corpus text) |
| `refs.bib` | the references in BibTeX form, checked against Crossref; the report carries them inline |

## The evaluation behind `results.tex`

Model 1 (`Congi-libya/samer-arat5v2-base-simplification`) was run once on the
locked SAMER and BAREC test sets (hashes checked against
`data/test_manifest.json`) and on DAASI's 350-pair held-out split:

- **Input prefix `بسّط: `** on every source — the model was trained with it
  (`model_traning.ipynb`, cell 10). `scripts/evaluation/predict.py` does not add
  it yet; without it the model scores twelve SARI points lower.
- Greedy decoding (what the phone runs), plus beam 4 on SAMER for comparison.
- BAREC and DAASI: tashkeel stripped from the source before the model sees it,
  as the application does; BAREC was also run raw, for comparison.
- Scored with `scripts/evaluation/score.py`, with its models moved to the GPU
  and repeated strings cached; output verified identical to the unmodified
  script on a sample.
