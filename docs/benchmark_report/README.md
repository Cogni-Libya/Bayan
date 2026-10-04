# Benchmark report

`bayan_benchmark_report.pdf` compares every simplifier we built (35 systems, dev and test) on the frozen
**BayanBench v2.0** rules. It also checks the meaning scorer against the human raters. Every number, table and figure in
it is generated from data: nothing is typed by hand, so a rerun rebuilds the whole report (#57).

## Pipeline

```
system outputs ──► Gemma 31B scores ──► collect.py ──► build/scores/{split}__{system}.json   (official scorecards)
(one jsonl per                (meaning + extra    analyse.py ──► build/analysis.json            (per-item values, human
 system and split)             questions)                                                       validation, examples)
                                                  figures.py ──► build/fig/*.pdf
                                                  tables.py  ──► build/tab/*.tex  (tables + the numbers quoted in the text)
                                                  latexmk    ──► bayan_benchmark_report.pdf
```

| file | what it does |
|---|---|
| `systems.py` | **the list of systems**: name, group, what it is, and where its dev and test outputs live. Also the meaning and extra score files to read. Add a system here and it appears in every table and figure. |
| `collect.py` | runs `bayanbench score` (v2.0) for every system and split, paired against today's app (`app-arat5`). Skips scorecards that already exist. |
| `analyse.py` | per-item meaning and simplicity values (with bayanbench's own measures and cluster bootstrap), the Gemma extra scores, scorer vs humans (confusion matrices, ROC, threshold sweep, calibration, Krippendorff's α, Cohen's κ), human ratings, training curves, and the Arabic examples |
| `figures.py`, `tables.py`, `common.py` | figures (matplotlib, vector PDF) and LaTeX tables, plus `macros.tex`, the numbers quoted in the text |
| `facts.json` | the few measurements that exist only in run logs: CPU latency, int8 checks on two CPUs, bundle sizes. Each row names its source. |
| `report.tex`, `Makefile` | the report (XeLaTeX, polyglossia, Amiri for the Arabic examples) |

## Requirements

- Python 3.10+ with `bayanbench[ease]` **v2.0** (`pip install "bayanbench[ease] @ git+https://github.com/Cogni-Libya/Bayan.git@main#subdirectory=bayanbench"`), `matplotlib`, `numpy`.
- A local snapshot of `Congi-libya/bayanbench-data` (private; `hf download Congi-libya/bayanbench-data --repo-type dataset`).
- Your licensed SAMER copy for the hard-word measures (optional; without it they are reported as not measured).
- XeLaTeX with `polyglossia`, `bidi`, `tcolorbox`, `booktabs`, the TeX Gyre Pagella font and the [Amiri](https://www.amirifont.org/) font.
- For step 2 only: a GPU with 44 GB or more (Gemma 4 31B int4 in vLLM). We used one RTX A6000 on vast.ai.

```bash
export BAYANBENCH_DATA=/path/to/bayanbench-data-snapshot     # items/, baselines/, ratings/, meaning/
export BAYAN_DATA=/path/to/data/processed/meaning_reward       # default: <repo>/data/processed/meaning_reward
export SAMER_DIR=/path/to/samer-simplification-corpus-v1       # optional
```

## Building the scorecards from scratch

### 1. System outputs

Each system needs one file per split with one line per bench item, `{"id": "<item id>", "output": "<what the reader
sees>"}`. `systems.py` says where each file is expected, relative to `$BAYAN_DATA` (or `bench:` for the data
snapshot). Generation needs **transformers 4.x** (4.57.6 tested): under 5.x AraT5's weights are untied and the outputs
come out garbled.

| systems | how the outputs are made |
|---|---|
| copy, today's app (dev and test), model 2 (dev) | already in the data snapshot: `baselines/{dev,test}/` |
| model 1, model 2 (test), AraBART on corpus v1, model 3 and model 3 + DPO greedy | `bayanbench predict --model <repo> --prefix "<prefix>" --split <split> -o <file>` |
| model 3 / retrain, float, greedy or beam 4, with and without the net | `scripts/meaning_reward/predict_net.py --model Congi-libya/bayan-arat5-v1 --prefix "بسط: " --backend hf [--num-beams 4] --out-plain <plain> --out-net <net>` (the retrain: `Congi-libya/bayan-arat5-v1-mix`) |
| model 3 int8 per-tensor | `scripts/meaning_reward/onnx_export.py`, then `predict_net.py --backend ort --model <out>/int8` |
| model 3 / retrain, **app int8** | the app's export recipe: `optimum-cli export onnx --task text2text-generation-with-past`, then onnxruntime `quantize_dynamic(QInt8, per_channel=True, op_types_to_quantize=["MatMul", "Gather"], extra_options={"EnableSubgraph": True})` on the encoder and the merged decoder; then `predict_net.py --backend ort --tokenizer <repo> [--num-beams 4]`. **Run it on a CPU with VNNI** (or ARM): on AVX2-only CPUs per-channel int8 saturates and the output is nonsense (report, Table 5). |
| hybrid decoding | `scripts/meaning_reward/hybrid_conf.py --model Congi-libya/bayan-arat5-v1 --prefix "بسط: " --out <dir>` (writes every share at once) |
| model 3 + DPO + net | `predict_net.py` with the DPO checkpoint |

Prefixes: «بسط: » for model 3, the retrain and model 2 AraBART; «بسّط: » (with the shadda) for model 2 AraT5. For model
2 add the tag (`[S2] `) or not, as the system name says. The `scripts/meaning_reward/` scripts are in PR #53.

### 2. Gemma 4 31B scores (GPU)

The bench never runs the scorer itself: it reads shared score files and reports any unscored output as **pending**.
List what is missing, then score it:

```bash
bayanbench meaning-pending <outputs.jsonl> --split <split> --data $BAYANBENCH_DATA --meaning-scores <your score files> -o pending.jsonl
bayanbench meaning pending.jsonl -o gemma-4-31b_new.jsonl                                   # same / added / missing / contradict
python scripts/meaning_reward/extra_questions.py --data $BAYANBENCH_DATA --preds dev:<a.jsonl> test:<b.jsonl> --out extra_new.jsonl   # Arabic / simpler / coherent
```

Add the new files to `MEANING` and `EXTRA` in `systems.py`; the shared `meaning/*.jsonl` of the data snapshot are read
automatically. The extra questions are not asked for track F (protected text), which should stay unchanged.

### 3. Scorecards and report

```bash
cd docs/benchmark_report
python collect.py                 # build/scores/*.json: one official scorecard per system and split (~1 h on 4 CPU cores)
make                              # analyse.py -> figures.py -> tables.py -> latexmk -> bayan_benchmark_report.pdf
```

`collect.py --only <system> --split test` rescores one system (delete its old `build/scores` file first). Each
scorecard is also saved as text (`build/scores/*.txt`), the same view as `bayanbench score` prints.

## Settings

- **Meaning kept** is v2.0's frozen rule: P(same) ≥ 0.5 and every number kept.
- **Joint rate** (meaning kept and simpler) is our own analysis setting, `--simpler-min 2,0.5` (2 clause words or half
  a level), because v2.0 leaves it undecided. The report labels it as such.
- **Intervals** are 95% cluster-bootstrap intervals over documents (bayanbench's `stats.ci`). Paired differences are
  against today's app on the same items.

## Data and privacy

`build/` is not committed. `analysis.json` holds BayanBench item text, which is private, and the scorecards are
cheap to rebuild. The PDF quotes a few bench items in its examples section, so keep it inside the team. No SAMER text
appears anywhere in the report.
