"""bayanbench: score dyslexia-friendly Arabic rewriting (v2: meaning from an open scorer, simpler as changes).

  bayanbench verify                                      check the benchmark data against its checksums
  bayanbench predict --model ID --prefix "بسط: " --split dev -o preds_dev.jsonl
  bayanbench score preds_dev.jsonl [--baseline other.jsonl] [--samer DIR] [--json out.json]
  bayanbench meaning-pending preds_dev.jsonl -o pending.jsonl   outputs the meaning scorer has not scored yet
  bayanbench meaning pending.jsonl -o my_scores.jsonl            score them (vLLM, a 44 GB+ GPU)

v1 judge tier (Gemini 3.1 Pro verdicts), an optional extra:
  bayanbench score preds_dev.jsonl --gemini
  bayanbench pending preds_dev.jsonl -o pending.jsonl    outputs no accepted judge has seen yet
  bayanbench judge pending.jsonl --backend gemini --model ID -o my_verdicts.jsonl
  bayanbench validate-judge my_verdicts_on_validation.jsonl

Common options: --data DIR (a local copy of Congi-libya/bayanbench-data), --split dev|test (default dev)."""
import argparse
import json
import sys
from pathlib import Path

from . import __version__
from .data import SETS, data_dir, load_items, load_predictions, manifest, read_jsonl, sha256, write_jsonl


def _utf8():
    # Windows consoles default to a legacy code page; Arabic output would fail or come out garbled
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def cmd_verify(a):
    d = data_dir(a.data, a.revision)
    m = manifest(d)
    bad = [f for f, h in m["files"].items() if sha256(Path(d) / f) != h]
    print(f"BayanBench data {m['version']} at {d}")
    for f in m["files"]:
        print(f"  {'OK ' if f not in bad else 'BAD'} {f}")
    from .meaning import config
    c = config(d)
    print("meaning scorer:", c["scorer"], "| threshold:", c["same_threshold"] if c["same_threshold"] is not None else "not frozen yet")
    print("v1 accepted judges:", ", ".join(m.get("accepted_judges", [])))
    if bad:
        raise SystemExit(f"{len(bad)} files do not match manifest.json")


def cmd_predict(a):
    from .predict import run
    d = data_dir(a.data, a.revision)
    items = load_items(d, a.split)
    rows = run(a.model, a.prefix, items, batch_size=a.batch_size, device=a.device, log=log)
    write_jsonl(a.out, rows)
    log(f"wrote {len(rows)} outputs to {a.out}")


def _ease(a, d, items, preds_list):
    lex = levels = None
    if not a.no_samer:
        from .ease import samer_lexicon
        lex = samer_lexicon(a.samer)
        if lex is None:
            log("hard words: not measured (no SAMER lexicon; pass --samer <your licensed SAMER folder> once)")
    if not a.no_level:
        from .ease import Levels
        levels = Levels(seed=Path(d) / "ease" / "sources.jsonl")
        texts = [it["source"] for it in items.values() if it["track"] not in ("C", "F")]
        for preds in preds_list:
            texts += [preds[i] for i, it in items.items() if it["track"] not in ("C", "F")]
        levels.measure(texts, log=log)
    return lex, levels


def cmd_score(a):
    from .meaning import Scores, config
    from .scoring import fmt, pending_summary, score
    d = data_dir(a.data, a.revision)
    items = load_items(d, a.split)
    preds = load_predictions(a.preds, items)
    base = load_predictions(a.baseline, items) if a.baseline else None
    lex, levels = _ease(a, d, items, [preds] + ([base] if base else []))
    cfg, notes = config(d), []
    if a.meaning_threshold is not None or a.contradict_threshold is not None or a.simpler_min:
        notes.append("thresholds set on the command line: your own analysis, not the official score")
    if a.meaning_threshold is not None:
        cfg["same_threshold"] = a.meaning_threshold
    if a.contradict_threshold is not None:
        cfg["contradict_threshold"] = a.contradict_threshold
    if a.simpler_min:
        cw, lv = a.simpler_min.split(",")
        cfg["simpler_min"] = {"clause_words": float(cw), "levels": float(lv)}
    if cfg["same_threshold"] is None:
        notes.append("meaning kept: the threshold is not frozen yet (#48); P(same meaning) only")
    joint = bool(a.joint and cfg["same_threshold"] is not None and cfg["simpler_min"])
    if a.joint and not joint:
        notes.append("joint rate: needs a frozen threshold and minimum change (or --meaning-threshold and --simpler-min)")
    sc = None if a.no_meaning else Scores(d, extra=a.meaning_scores or [])
    v = None
    if a.gemini:
        from .verdicts import Verdicts
        v = Verdicts(d, extra=a.verdicts or [], accepted=a.accept_judge or None)
    res = score(items, preds, sc, lex, levels, baseline=base, sets=a.set or SETS, cfg=cfg, verdicts=v, joint=joint)
    m = manifest(d)
    res.update({"split": a.split, "predictions": str(a.preds), "baseline": str(a.baseline) if a.baseline else None,
                "data_version": m["version"], "bayanbench": __version__, "meaning": cfg,
                "accepted_judges": sorted(v.accepted) if v else None,
                "hard_words_measured": lex is not None, "reading_level_measured": levels is not None})
    print(fmt(res, f"BayanBench {m['version']}, {a.split}: {a.preds}  (rate % or mean [95% interval])",
              Path(a.baseline).stem if a.baseline else None, notes))
    pend = {s: p for s, p in pending_summary(res).items() if any(p.values())}
    if pend:
        print(f"\npending item-measures: {pend}. `bayanbench meaning-pending` lists the outputs to score.")
    if a.json:
        Path(a.json).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


def cmd_meaning_pending(a):
    from .meaning import Scores
    d = data_dir(a.data, a.revision)
    items = load_items(d, a.split)
    pend = Scores(d, extra=a.meaning_scores or []).pending(items, load_predictions(a.preds, items))
    write_jsonl(a.out, pend)
    log(f"{len(pend)} outputs without a meaning score -> {a.out}")


def cmd_meaning(a):
    from .meaning import MODEL, run
    run(read_jsonl(a.pairs), a.out, model=a.model or MODEL, questions=tuple(a.questions.split(",")),
        gpu_util=a.gpu_util, log=log)


def cmd_pending(a):
    from .verdicts import Verdicts
    d = data_dir(a.data, a.revision)
    items = load_items(d, a.split)
    pend = Verdicts(d, extra=a.verdicts or []).pending(items, load_predictions(a.preds, items))
    write_jsonl(a.out, pend)
    log(f"{len(pend)} outputs without an accepted verdict -> {a.out}")


def cmd_judge(a):
    from .judge import run
    d = data_dir(a.data, a.revision)
    run(read_jsonl(a.pairs), d, a.backend, a.model, a.out, base_url=a.base_url, batch=a.batch, workers=a.workers, log=log)


def cmd_validate_judge(a):
    from .validate import report
    d = data_dir(a.data, a.revision)
    print(json.dumps(report(d, a.verdicts), ensure_ascii=False, indent=1))


def main(argv=None):
    _utf8()
    p = argparse.ArgumentParser(prog="bayanbench", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=__version__)
    sub = p.add_subparsers(dest="cmd", required=True)

    def common(sp, split=True):
        sp.add_argument("--data", help="local copy of the benchmark data (default: download Congi-libya/bayanbench-data)")
        sp.add_argument("--revision", help="data version (git revision of the dataset repo)")
        if split:
            sp.add_argument("--split", default="dev", choices=["dev", "test"])

    sp = sub.add_parser("verify", help="check the benchmark data against its checksums"); common(sp, False)
    sp.set_defaults(fn=cmd_verify)

    sp = sub.add_parser("predict", help="run a Hugging Face seq2seq model the way the app runs it"); common(sp)
    sp.add_argument("--model", required=True, help="Hugging Face id or local folder")
    sp.add_argument("--prefix", required=True, help='input prefix, with any tag the model was trained with, e.g. "بسط: [S2] "')
    sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--batch-size", type=int, default=24)
    sp.add_argument("--device", help="cuda, cpu (default: cuda if available)")
    sp.set_defaults(fn=cmd_predict)

    sp = sub.add_parser("score", help="scorecard for one predictions file"); common(sp)
    sp.add_argument("preds")
    sp.add_argument("--baseline", help="another predictions file: paired differences on the same items")
    sp.add_argument("--set", action="append", choices=SETS, help="only these item sets (repeatable)")
    sp.add_argument("--samer", help="your licensed SAMER corpus folder (for the hard-word measures; read once, cached)")
    sp.add_argument("--no-samer", action="store_true", help="skip the hard-word measures")
    sp.add_argument("--no-level", action="store_true", help="skip the reading-level measures (no torch needed)")
    sp.add_argument("--meaning-scores", action="append", help="extra meaning score files (records name their scorer)")
    sp.add_argument("--no-meaning", action="store_true", help="skip the meaning measures")
    sp.add_argument("--meaning-threshold", type=float, help="P(same) threshold for 'meaning kept' (analysis only)")
    sp.add_argument("--contradict-threshold", type=float, help="P(contradict) over which a flagged pair fails (analysis only)")
    sp.add_argument("--simpler-min", help="CLAUSE_WORDS,LEVELS: minimum change that counts as simpler (analysis only)")
    sp.add_argument("--joint", action="store_true", help="also show the joint rate: meaning kept and simpler")
    sp.add_argument("--gemini", action="store_true", help="also show the v1 judge tier (Gemini verdicts)")
    sp.add_argument("--verdicts", action="append", help="--gemini: extra verdict files to read (only accepted judges count)")
    sp.add_argument("--accept-judge", action="append", help="--gemini: count this judge too (your own analysis)")
    sp.add_argument("--json", help="also write the full result as JSON")
    sp.set_defaults(fn=cmd_score)

    sp = sub.add_parser("meaning-pending", help="outputs the meaning scorer has not scored yet"); common(sp)
    sp.add_argument("preds"); sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--meaning-scores", action="append", help="extra score files to take into account")
    sp.set_defaults(fn=cmd_meaning_pending)

    sp = sub.add_parser("meaning", help="score pending outputs for meaning (vLLM, a 44 GB+ GPU)")
    sp.add_argument("pairs", help="file from `bayanbench meaning-pending`")
    sp.add_argument("-o", "--out", required=True, help="score file to append to (resumable)")
    sp.add_argument("--model", help="default: the official scorer, google/gemma-4-31B-it-qat-w4a16-ct")
    sp.add_argument("--questions", default="same,added,missing,contradict")
    sp.add_argument("--gpu-util", type=float, default=0.88)
    sp.set_defaults(fn=cmd_meaning)

    sp = sub.add_parser("pending", help="v1: outputs that no accepted Gemini judge has seen yet"); common(sp)
    sp.add_argument("preds"); sp.add_argument("-o", "--out", required=True)
    sp.add_argument("--verdicts", action="append", help="extra verdict files to take into account")
    sp.set_defaults(fn=cmd_pending)

    sp = sub.add_parser("judge", help="v1: judge pending outputs with Gemini (needs judge access)"); common(sp, False)
    sp.add_argument("pairs", help="file from `bayanbench pending` (or judge/validation.jsonl to validate a judge)")
    sp.add_argument("--backend", required=True, choices=["gemini", "openai", "agy"])
    sp.add_argument("--model", required=True)
    sp.add_argument("--base-url", help="openai backend: server URL, e.g. http://localhost:8080/v1")
    sp.add_argument("-o", "--out", required=True, help="verdict file to append to (resumable)")
    sp.add_argument("--batch", type=int, default=10, help="pairs per call (the shared verdicts used 10)")
    sp.add_argument("--workers", type=int, default=2)
    sp.set_defaults(fn=cmd_judge)

    sp = sub.add_parser("validate-judge", help="v1: how far a judge's verdicts agree with known answers"); common(sp, False)
    sp.add_argument("verdicts", help="that judge's verdicts on judge/validation.jsonl")
    sp.set_defaults(fn=cmd_validate_judge)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
