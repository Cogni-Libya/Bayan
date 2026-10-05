"""Every system in the report: where its BayanBench outputs live, and what it is.

Paths are relative to BAYAN_DATA (default: <repo>/data/processed/meaning_reward) or to the BayanBench data snapshot
(prefix "bench:"). Each system has a dev and/or test output file: one {"id", "output"} line per item."""
import os
from pathlib import Path

ROOT = Path(os.environ.get("BAYAN_DATA", Path(__file__).resolve().parents[2] / "data/processed/meaning_reward"))
BENCH = Path(os.environ.get("BAYANBENCH_DATA", ""))  # local snapshot of Congi-libya/bayanbench-data
SAMER = os.environ.get("SAMER_DIR")                  # licensed SAMER copy (hard-word measures); optional

# key: (label, group, description, dev path, test path)
SYSTEMS = {
 "copy":          ("Copy (no change)", "reference", "the selection unchanged", "bench:baselines/dev/copy.jsonl", "compare/arpreds/test__copy.jsonl"),
 "app-arat5":     ("App today: AraT5 (int8)", "app", "shipped app, model 2 AraT5v2, int8, no tag", "bench:baselines/dev/app-arat5.jsonl", "bench:baselines/test/app-arat5.jsonl"),
 "app-arabart":   ("App today: AraBART (int8)", "app", "shipped app, model 2 AraBART, int8, no tag", "bench:baselines/dev/app-arabart.jsonl", "bench:baselines/test/app-arabart.jsonl"),
 "model1":        ("Model 1", "model 1-2", "AraT5v2 on SAMER", "compare/out/bench_preds/dev__model1.jsonl", "compare/out/bench_preds/test__model1.jsonl"),
 "m2-arat5":      ("Model 2 AraT5 [S2]", "model 1-2", "model 2 AraT5v2, strength tag [S2], float", "bench:baselines/dev/model2-arat5.jsonl", "compare/arpreds/test__model2-arat5.jsonl"),
 "m2-arat5-nt":   ("Model 2 AraT5 no tag", "model 1-2", "model 2 AraT5v2, no tag, float", "bench:baselines/dev/model2-arat5-notag.jsonl", "compare/arpreds/test__model2-arat5-notag.jsonl"),
 "m2-arabart":    ("Model 2 AraBART [S2]", "model 1-2", "model 2 AraBART, tag [S2], float", "bench:baselines/dev/model2-arabart.jsonl", "compare/arpreds/test__model2-arabart.jsonl"),
 "m2-arabart-nt": ("Model 2 AraBART no tag", "model 1-2", "model 2 AraBART, no tag, float", "bench:baselines/dev/model2-arabart-notag.jsonl", "compare/arpreds/test__model2-arabart-notag.jsonl"),
 "v1-arabart":    ("AraBART on corpus v1", "model 3 family", "AraBART, corpus v1, MLE (MRT baseline)", "compare/out/bench_preds/dev__v1-mle-arabart.jsonl", "compare/out/bench_preds/test__v1-mle-arabart.jsonl"),
 "m3":            ("Model 3 greedy", "model 3 family", "AraT5v2 on corpus v1, float, greedy", "mix/out_all/out/dev__model3-float.jsonl", "mix/out_all/out/test__model3-float.jsonl"),
 "m3-net":        ("Model 3 greedy + net", "model 3 family", "float, greedy, safety net", "mix/out_all/out/dev__model3-float-net.jsonl", "mix/out_all/out/test__model3-float-net.jsonl"),
 "m3-b4":         ("Model 3 beam 4", "model 3 family", "float, beam 4", "mix/out_all/outD/dev__model3-beam4.jsonl", "mix/out_all/outD/test__model3-beam4.jsonl"),
 "m3-b4-net":     ("Model 3 beam 4 + net", "model 3 family", "float, beam 4, safety net", "mix/out_all/outD/dev__model3-beam4-net.jsonl", "mix/out_all/outD/test__model3-beam4-net.jsonl"),
 "m3-dpo":        ("Model 3 + DPO", "model 3 family", "model 3 + student DPO (dropped)", "compare/arpreds/dev__model3-dpo.jsonl", "compare/arpreds/test__model3-dpo.jsonl"),
 "m3-dpo-net":    ("Model 3 + DPO + net", "model 3 family", "model 3 + DPO, safety net (dropped)", "safetynet/dev__arat5-v1-dpo-netA.jsonl", "safetynet/test__arat5-v1-dpo-netA.jsonl"),
 "m3-pt":         ("Model 3 int8 per-tensor", "int8", "per-tensor int8, greedy", "mix/out_all/out/dev__model3-int8.jsonl", "mix/out_all/out/test__model3-int8.jsonl"),
 "m3-pt-net":     ("Model 3 int8 per-tensor + net", "int8", "per-tensor int8, greedy, net", "mix/out_all/out/dev__model3-int8-net.jsonl", "mix/out_all/out/test__model3-int8-net.jsonl"),
 "m3-q":          ("Model 3 app int8 greedy", "int8", "app recipe (per-channel int8), greedy", "final/out_all/out2/dev__m3-int8pc-g.jsonl", "final/out_all/out2/test__m3-int8pc-g.jsonl"),
 "m3-q-net":      ("Model 3 app int8 greedy + net", "int8", "app int8, greedy, net", "final/out_all/out2/dev__m3-int8pc-g-net.jsonl", "final/out_all/out2/test__m3-int8pc-g-net.jsonl"),
 "m3-q-b4":       ("Model 3 app int8 beam 4", "int8", "app int8, beam 4", "final/out_all/out2/dev__m3-int8pc-b4.jsonl", "final/out_all/out2/test__m3-int8pc-b4.jsonl"),
 "m3-q-b4-net":   ("Model 3 app int8 beam 4 + net (ship)", "int8", "app int8, beam 4, net: the shipping candidate", "final/out_all/out2/dev__m3-int8pc-b4-net.jsonl", "final/out_all/out2/test__m3-int8pc-b4-net.jsonl"),
 "rt":            ("Retrain greedy", "retrain", "fluency retrain, float, greedy", "mix/out_all/out/dev__model3-mix.jsonl", "mix/out_all/out/test__model3-mix.jsonl"),
 "rt-net":        ("Retrain greedy + net", "retrain", "float, greedy, net", "mix/out_all/out/dev__model3-mix-net.jsonl", "mix/out_all/out/test__model3-mix-net.jsonl"),
 "rt-b4":         ("Retrain beam 4", "retrain", "float, beam 4", "final/out_all/out2/dev__mix-beam4.jsonl", "final/out_all/out2/test__mix-beam4.jsonl"),
 "rt-b4-net":     ("Retrain beam 4 + net", "retrain", "float, beam 4, net", "final/out_all/out2/dev__mix-beam4-net.jsonl", "final/out_all/out2/test__mix-beam4-net.jsonl"),
 "rt-q":          ("Retrain app int8 greedy", "retrain", "app int8, greedy", "final/out_all/out2/dev__mix-int8pc-g.jsonl", "final/out_all/out2/test__mix-int8pc-g.jsonl"),
 "rt-q-net":      ("Retrain app int8 greedy + net", "retrain", "app int8, greedy, net", "final/out_all/out2/dev__mix-int8pc-g-net.jsonl", "final/out_all/out2/test__mix-int8pc-g-net.jsonl"),
 "rt-q-b4":       ("Retrain app int8 beam 4", "retrain", "app int8, beam 4", "final/out_all/out2/dev__mix-int8pc-b4.jsonl", "final/out_all/out2/test__mix-int8pc-b4.jsonl"),
 "rt-q-b4-net":   ("Retrain app int8 beam 4 + net", "retrain", "app int8, beam 4, net", "final/out_all/out2/dev__mix-int8pc-b4-net.jsonl", "final/out_all/out2/test__mix-int8pc-b4-net.jsonl"),
}
for _p in (0, 10, 20, 30, 50, 100):
    SYSTEMS[f"hyb{_p}"] = (f"Model 3 hybrid {_p}% beam", "hybrid", f"float greedy, beam 4 on the {_p}% least confident sentences",
                           f"mix/out_all/out_h/dev__model3-hyb{_p}.jsonl", f"mix/out_all/out_h/test__model3-hyb{_p}.jsonl")

# Gemma 4 31B meaning scores (4 questions) and extra scores (Arabic / simpler / coherent), every file we made
MEANING = ["step1/out/gemma-4-31b_test.jsonl", "step3/out/gemma-4-31b_step3.jsonl", "step4/out/gemma-4-31b_step4.jsonl",
           "compare/out/gemma-4-31b_compare.jsonl", "step6/out/gemma-4-31b_step6.jsonl", "step6/out/gemma-4-31b_stageD.jsonl",
           "mix/out_all/gemma-4-31b_mix.jsonl", "mix/out_all/gemma-4-31b_hyb.jsonl", "final/prev_final.jsonl",
           "final/out_all/gemma-4-31b_final.jsonl", "report/gemma-4-31b_report.jsonl"]
EXTRA = ["compare/out/gemma-4-31b_extra.jsonl", "step6/out/extra_step6.jsonl", "step6/out/extra_stageD.jsonl",
         "mix/out_all/extra_mix.jsonl", "mix/out_all/extra_hyb.jsonl", "final/out_all/extra_final.jsonl", "report/extra_report.jsonl"]


def path(p):
    return BENCH / p[6:] if p.startswith("bench:") else ROOT / p


def outputs(split):
    """{key: path} of the systems that have an output file for this split."""
    return {k: path(v[3 if split == "dev" else 4]) for k, v in SYSTEMS.items() if path(v[3 if split == "dev" else 4]).exists()}


def meaning_files():
    return [ROOT / f for f in MEANING if (ROOT / f).exists()] + sorted((BENCH / "meaning").glob("*.jsonl"))


def extra_files():
    return [ROOT / f for f in EXTRA if (ROOT / f).exists()]
