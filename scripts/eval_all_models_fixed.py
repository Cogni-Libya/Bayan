#!/usr/bin/env python3
"""Reproducible Arabic diacritization benchmark.

The benchmark deliberately runs each heavyweight model in a subprocess.  This
keeps the CAMeL MLE resources and the CATT ONNX sessions from competing for
the small runner memory limit.

Datasets:
* Official CATT/Tashkeela benchmark snapshot, pinned to the CATT repository
  commit used by this run.
* The supplied SAMER 100-sentence file for exact base-letter preservation.
* The supplied manual_check_30 file.  It contains inputs and historical model
  outputs, but no human gold labels; therefore an objective manual-error count
  cannot be recomputed from it.
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import ssl
import subprocess
import sys
import time
import unicodedata
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
RAW_RESULTS = RESULTS / "benchmark_raw"
DATA = ROOT / "data"

TASHKEELA_COMMIT = "8d5330499feb85f6625e6af632141ed2ed6065fd"
TASHKEELA_URL = (
    "https://raw.githubusercontent.com/abjadai/catt/"
    f"{TASHKEELA_COMMIT}/benchmarking/all_models_CATT_data/CATT_data_gt.txt"
)

ARABIC_MARKS = set(chr(c) for c in range(0x064B, 0x0653)) | {"\u0670"}
ARABIC_LETTER_RE = re.compile(r"[\u0621-\u063A\u0641-\u064A\u0671]")
WHITESPACE_RE = re.compile(r"\s+|\S+")

MODEL_LABELS = {
    "camel": "CAMeL Tools MLE",
    "catt": "CATT Encoder-Only",
    "mishkal": "Mishkal",
    "libtashkeel": "Libtashkeel (text2tashkeel wrapper)",
}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def is_arabic_letter(ch: str) -> bool:
    return bool(ch) and bool(ARABIC_LETTER_RE.fullmatch(ch))


def canonical_letter(ch: str) -> str:
    # This is the normalization used only for DER/WER alignment.  Exact
    # base-letter preservation is scored separately and does not normalize.
    return {"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"}.get(ch, ch)


def mark_order(marks: str) -> str:
    # Put shadda first, matching the CATT tokenizer and standard Arabic
    # rendering conventions.
    if "\u0651" in marks:
        return "\u0651" + marks.replace("\u0651", "")
    return marks


def letter_units(text: str) -> list[tuple[str, str]]:
    """Return (base Arabic letter, attached marks) pairs."""
    text = nfc(text)
    out: list[tuple[str, str]] = []
    pending = ""
    for ch in text:
        if ch in ARABIC_MARKS:
            pending += ch
        else:
            if is_arabic_letter(ch):
                out.append((ch, mark_order(pending)))
            pending = ""
    return out


def word_units(text: str) -> list[list[tuple[str, str]]]:
    """Split into Arabic words while retaining marks."""
    text = nfc(text)
    words: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    pending = ""
    for ch in text:
        if ch in ARABIC_MARKS:
            pending += ch
            continue
        if is_arabic_letter(ch):
            current.append((ch, mark_order(pending)))
            pending = ""
        else:
            pending = ""
            if current:
                words.append(current)
                current = []
    if current:
        words.append(current)
    return words


def strip_case(units: list[tuple[str, str]], text: str) -> list[tuple[str, str]]:
    """Remove the mark on the final Arabic letter of each whitespace word."""
    # Word boundaries are represented by the word splitter, so the last
    # letter in each returned word is the case-ending position.
    words = word_units(text)
    flat: list[tuple[str, str]] = []
    for word in words:
        flat.extend(word[:-1])
        if word:
            flat.append((word[-1][0], ""))
    return flat


def align_marks(
    ref: list[tuple[str, str]],
    pred: list[tuple[str, str]],
    ignore_case: bool,
) -> tuple[int, int]:
    """Score marks with a base-letter alignment, not raw string positions."""
    rbase = [canonical_letter(ch) for ch, _ in ref]
    pbase = [canonical_letter(ch) for ch, _ in pred]
    sm = difflib.SequenceMatcher(a=rbase, b=pbase, autojunk=False)
    wrong = 0
    total = len(ref)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for ri, pj in zip(range(i1, i2), range(j1, j2)):
                rm = ref[ri][1]
                pm = pred[pj][1]
                if ignore_case:
                    # The caller already supplies word-level units for the
                    # no-case path; this branch is retained for safety.
                    rm = pm = ""
                if rm != pm:
                    wrong += 1
        elif tag == "replace":
            for ri, pj in zip(range(i1, i2), range(j1, j2)):
                rm = ref[ri][1]
                pm = pred[pj][1]
                if ignore_case:
                    rm = pm = ""
                if rm != pm:
                    wrong += 1
            wrong += max(0, (i2 - i1) - (j2 - j1))
        elif tag == "delete":
            wrong += i2 - i1
        # Insertions have no gold position and therefore no DER denominator.
    return wrong, total


def score_der(ref_text: str, pred_text: str, ignore_case: bool = False) -> tuple[int, int]:
    if not ignore_case:
        return align_marks(letter_units(ref_text), letter_units(pred_text), False)
    ref = strip_case(letter_units(ref_text), ref_text)
    pred = strip_case(letter_units(pred_text), pred_text)
    # strip_case has already removed case-ending marks.  Do not blank every
    # remaining mark in align_marks: that would make the no-case DER
    # trivially zero for every model.
    return align_marks(ref, pred, False)


def word_signature(word: list[tuple[str, str]]) -> str:
    return "".join(canonical_letter(ch) for ch, _ in word)


def score_wer(ref_text: str, pred_text: str) -> tuple[int, int]:
    ref_words = word_units(ref_text)
    pred_words = word_units(pred_text)
    ra = [word_signature(w) for w in ref_words]
    pa = [word_signature(w) for w in pred_words]
    sm = difflib.SequenceMatcher(a=ra, b=pa, autojunk=False)
    wrong = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for rw, pw in zip(ref_words[i1:i2], pred_words[j1:j2]):
                if align_marks(rw, pw, False)[0]:
                    wrong += 1
        elif tag == "replace":
            pairs = min(i2 - i1, j2 - j1)
            for k in range(pairs):
                if (
                    word_signature(ref_words[i1 + k])
                    != word_signature(pred_words[j1 + k])
                    or align_marks(ref_words[i1 + k], pred_words[j1 + k], False)[0]
                ):
                    wrong += 1
            wrong += max(0, (i2 - i1) - pairs)
        elif tag == "delete":
            wrong += i2 - i1
    return wrong, len(ref_words)


def exact_base_signature(text: str) -> list[str]:
    return [ch for ch in nfc(text) if is_arabic_letter(ch)]


def download_dataset(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return
    ctx = ssl._create_unverified_context()
    req = Request(TASHKEELA_URL, headers={"User-Agent": "diacritization-benchmark/1.0"})
    with urlopen(req, context=ctx, timeout=60) as response:
        path.write_bytes(response.read())


def parse_manual_inputs(path: Path) -> list[str]:
    inputs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("  Input :"):
            inputs.append(line.split(":", 1)[1].strip())
    return inputs[:30]


def read_lines(path: Path) -> list[str]:
    return [line.rstrip("\n\r") for line in path.read_text(encoding="utf-8").splitlines()]


def model_output(model: str, lines: list[str]) -> list[str]:
    if model == "catt":
        from catt_tashkeel import CATTEncoderOnly

        runner = CATTEncoderOnly()
        # The package's batched decoder is substantially faster than invoking
        # a fresh encoder/decoder loop for every sentence.
        return [
            x.replace("\n", " ")
            for x in runner.do_tashkeel_batch(lines, batch_size=16, verbose=False)
        ]

    if model == "camel":
        from camel_tools.cli.camel_diac import _diac_tokens
        from camel_tools.disambig.mle import MLEDisambiguator
        from camel_tools.tokenizers.word import simple_word_tokenize

        runner = MLEDisambiguator.pretrained("calima-msa-r13")
        out = []
        for line in lines:
            toks = WHITESPACE_RE.findall(line)
            out.append(
                "".join(
                    _diac_tokens(
                        toks,
                        runner,
                        ignore_markers=True,
                        marker="@@IGNORE@@",
                        strip_markers=True,
                        pretokenized=False,
                    )
                ).replace("\n", " ")
            )
        return out

    if model == "mishkal":
        from mishkal.tashkeel import TashkeelClass

        runner = TashkeelClass()
        runner.enabled_verbose = False
        return [runner.tashkeel(x).replace("\n", " ") for x in lines]

    if model == "libtashkeel":
        from text2tashkeel import Diacritizer

        runner = Diacritizer("libtashkeel")
        return [runner.diacritize(x).replace("\n", " ") for x in lines]

    raise ValueError(model)


def worker(args: argparse.Namespace) -> int:
    lines = read_lines(Path(args.input))
    started = time.perf_counter()
    outputs = model_output(args.worker_model, lines)
    elapsed = time.perf_counter() - started
    if len(outputs) != len(lines):
        raise RuntimeError(
            f"{args.worker_model} returned {len(outputs)} lines for {len(lines)} inputs"
        )
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text("\n".join(outputs) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {"model": args.worker_model, "lines": len(lines), "seconds": elapsed},
            ensure_ascii=False,
        )
    )
    return 0


def run_worker(model: str, name: str, lines: list[str]) -> tuple[list[str], float]:
    input_path = RAW_RESULTS / f"{name}.input.txt"
    output_path = RAW_RESULTS / f"{model}.{name}.txt"
    input_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker-model",
        model,
        "--input",
        str(input_path),
        "--output",
        str(output_path),
    ]
    proc = subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True)
    if proc.returncode:
        print(proc.stdout, end="")
        print(proc.stderr, end="", file=sys.stderr)
        raise RuntimeError(f"{model} worker failed with exit code {proc.returncode}")
    info = json.loads(proc.stdout.strip().splitlines()[-1])
    return read_lines(output_path), float(info["seconds"])


def pct(wrong: int, total: int) -> str:
    return f"{(100.0 * wrong / total):.2f}%" if total else "—"


def sentence_metrics(refs: list[str], preds: list[str]) -> dict[str, float | int]:
    if len(refs) != len(preds):
        raise ValueError("reference/prediction length mismatch")
    totals = {
        "der_wrong": 0,
        "der_total": 0,
        "der_nc_wrong": 0,
        "der_nc_total": 0,
        "wer_wrong": 0,
        "wer_total": 0,
    }
    corrupt = 0
    for ref, pred in zip(refs, preds):
        a, b = score_der(ref, pred, False)
        c, d = score_der(ref, pred, True)
        e, f = score_wer(ref, pred)
        totals["der_wrong"] += a
        totals["der_total"] += b
        totals["der_nc_wrong"] += c
        totals["der_nc_total"] += d
        totals["wer_wrong"] += e
        totals["wer_total"] += f
        if exact_base_signature(ref) != exact_base_signature(pred):
            corrupt += 1
    totals["base_corrupt_sentences"] = corrupt
    totals["base_corrupt_rate"] = 100.0 * corrupt / len(refs) if refs else 0.0
    totals["der"] = 100.0 * totals["der_wrong"] / totals["der_total"] if totals["der_total"] else 0.0
    totals["der_nc"] = (
        100.0 * totals["der_nc_wrong"] / totals["der_nc_total"]
        if totals["der_nc_total"]
        else 0.0
    )
    totals["wer"] = 100.0 * totals["wer_wrong"] / totals["wer_total"] if totals["wer_total"] else 0.0
    return totals


def first_error(ref: str, pred: str) -> str:
    rb = exact_base_signature(ref)
    pb = exact_base_signature(pred)
    if rb != pb:
        if len(rb) != len(pb):
            return f"Base-letter sequence length changed ({len(rb)} → {len(pb)}; inserted/deleted character)"
        for a, b in zip(rb, pb):
            if a != b:
                if canonical_letter(a) == canonical_letter(b):
                    return f"Base-letter variant changed ({a} → {b})"
                return f"Base letter changed ({a} → {b})"
        return "Base-letter sequence changed"
    ru = letter_units(ref)
    pu = letter_units(pred)
    sm = difflib.SequenceMatcher(
        a=[canonical_letter(c) for c, _ in ru],
        b=[canonical_letter(c) for c, _ in pu],
        autojunk=False,
    )
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in {"equal", "replace"}:
            for ri, pj in zip(range(i1, i2), range(j1, j2)):
                if ru[ri][1] != pu[pj][1]:
                    return (
                        f"Wrong/missing diacritic on '{ru[ri][0]}' "
                        f"(expected {ru[ri][1] or 'none'}, got {pu[pj][1] or 'none'})"
                    )
    return "Diacritics differ from the reference"


def example_block(model: str, raw: list[str], preds: list[str], refs: list[str] | None = None) -> str:
    examples: list[str] = []
    for idx, pred in enumerate(preds):
        ref = refs[idx] if refs else raw[idx]
        if exact_base_signature(ref) == exact_base_signature(pred) and letter_units(ref) == letter_units(pred):
            continue
        examples.append(
            f"### Example {len(examples) + 1}\n"
            f"- **Raw Input:** {raw[idx][:500]}\n"
            f"- **Model Output:** {pred[:500]}\n"
            f"- **Specific Error Type:** {first_error(ref, pred)}"
        )
        if len(examples) == 5:
            break
    if not examples:
        examples.append("No differing example was produced in the evaluated sample.")
    return f"### {MODEL_LABELS[model]}\n\n" + "\n\n".join(examples)


def environment_note() -> str:
    return (
        "The benchmark was run in `.venv_camel` with Python "
        f"{sys.version.split()[0]}. `libtashkeel` is not published on the "
        "configured PyPI index and its Rust source could not be built because "
        "Rust/cargo is unavailable; the benchmark therefore uses the "
        "`libtashkeel` ONNX model through the installed `text2tashkeel` "
        "wrapper. CATT model archives were downloaded from the pinned CATT "
        "release because the package's default HTTPS certificate check failed "
        "in this environment."
    )


def write_report(
    official: list[str],
    samer: list[str],
    manual_inputs: list[str],
    outputs: dict[str, dict[str, list[str]]],
    timings: dict[str, dict[str, float]],
) -> None:
    official_metrics = {m: sentence_metrics(official, outputs[m]["official"]) for m in MODEL_LABELS}
    samer_metrics = {m: sentence_metrics(samer, outputs[m]["samer"]) for m in MODEL_LABELS}
    manual_note = (
        "Not independently scorable from the supplied file: "
        "`manual_check_30.txt` contains 30 raw inputs plus historical model "
        "outputs, but no expert gold annotations. The historical 28/30 and "
        "16/30 figures are retained below as reported context only."
    )

    lines: list[str] = [
        "# Arabic Diacritization Benchmark Report",
        "",
        "**DER/WER corpus:** Official Tashkeela Test Split, using the CATT "
        "benchmark fixture snapshot "
        f"({len(official)} sentences; pinned CATT commit `{TASHKEELA_COMMIT[:12]}`).",
        "**Base-letter corpus:** Supplied SAMER 100-sentence corpus.",
        "**Manual review input:** Supplied `manual_check_30.txt` (30 inputs; no gold labels).",
        "**Evaluation runner:** `scripts/eval_all_models_fixed.py`.",
        "",
        "---",
        "",
        "## 1. Quantitative Benchmark & Practical Measures",
        "",
        "| Model | DER (w/ case) | DER (w/o case) | WER | SAMER base-letter corruption | CPU throughput (sent/sec) | Size / runtime footprint | License | Phone / browser ready? | Manual errors (out of 30) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | :--- | :--- | :--- | :--- |",
    ]
    manual_values = {
        "camel": "Not scorable*",
        "catt": "Not scorable*",
        "mishkal": "28/30†",
        "libtashkeel": "16/30†",
    }
    deployment = {
        "camel": (
            "~1,500 MB",
            "MIT / GPLv2 model resources",
            "❌ No (requires PyTorch, Python runtime, and morphology catalogs)",
        ),
        "catt": (
            "~1,500 MB environment footprint",
            "Apache-2.0 / CC BY-NC 4.0 model",
            "❌ No (requires Python runtime and ONNX/model integration)",
        ),
        "mishkal": (
            "~25 MB",
            "GPLv3",
            "⚠️ Partial (rule-based; requires Python/Pyodide wrapper)",
        ),
        "libtashkeel": (
            "~45 MB in the prior assessment; 4.8 MB model downloaded here",
            "MIT",
            "✅ Yes (exportable to ONNX Mobile / WebAssembly)",
        ),
    }
    for model in MODEL_LABELS:
        om = official_metrics[model]
        sm = samer_metrics[model]
        throughput = len(official) / timings[model]["official"] if timings[model]["official"] else 0
        size, license_name, readiness = deployment[model]
        lines.append(
            f"| **{MODEL_LABELS[model]}** | {om['der']:.2f}% | {om['der_nc']:.2f}% | "
            f"{om['wer']:.2f}% | {sm['base_corrupt_rate']:.2f}% "
            f"({sm['base_corrupt_sentences']}/{len(samer)}) | {throughput:.2f} | "
            f"{size} | {license_name} | {readiness} | {manual_values[model]} |"
        )
    lines += [
        "",
        f"*{environment_note()}*",
        "",
        "\\* A manual error count requires human gold labels. Counting disagreement "
        "between two model outputs would not be a valid manual accuracy measure.",
        "",
        "† These two counts are the historical human-review figures printed in the "
        "attached report; they were not recomputed because the supplied file has "
        "no gold annotation. They should not be compared to the empirical DER/WER "
        "numbers as if they were automatically measured.",
        "",
        "### Metric definition",
        "",
        "DER is the fraction of Arabic-letter positions whose attached harakat "
        "differ from the reference. The w/o-case score ignores the mark on the "
        "last Arabic letter of each whitespace-delimited word. Common alif "
        "variants are normalized only for DER/WER alignment; SAMER corruption "
        "uses exact Arabic base-letter sequences and therefore detects those "
        "changes, deletion, and insertion.",
        "",
        "## 2. Practical Feasibility Summary",
        "",
        "* **Libtashkeel:** The tested model is a small ONNX model accessed through "
        "the `text2tashkeel` Python wrapper. It does not require PyTorch at "
        "inference time and is the most straightforward candidate for mobile or "
        "browser packaging, subject to validating the wrapper/model license.",
        "* **Mishkal:** Rule-based and comparatively light, but GPL-licensed and "
        "dependent on a Python rule-engine stack.",
        "* **CAMeL Tools MLE:** Requires the CAMeL Python runtime, PyTorch "
        "environment, and downloaded morphology/disambiguation resources; it is "
        "not a direct phone/browser artifact.",
        "* **CATT:** The ONNX release is runnable on CPU, but its model files are "
        "much heavier than the Libtashkeel model and still require an ONNX "
        "runtime integration for mobile/browser deployment.",
        "",
        "## 3. Qualitative Observations",
        "",
        "The SAMER base-letter rate is a structural-integrity measure, not a "
        "diacritic-quality score. A model can have a low DER while still "
        "changing input spelling; the two measurements are intentionally kept "
        "separate.",
        "",
        "## Qualitative Failure & Corruption Examples",
        "",
    ]
    for model in MODEL_LABELS:
        lines.append(
            example_block(
                model,
                [re.sub(f"[{''.join(sorted(ARABIC_MARKS))}]", "", x) for x in official],
                outputs[model]["official"],
                official,
            )
        )
        lines.append("")
    lines += [
        "## 4. Reproducibility",
        "",
        "The runner creates the pinned Tashkeela/CATT test snapshot under "
        "`data/tashkeela_test.txt`, runs each model in an isolated subprocess, "
        "and stores raw predictions under `results/benchmark_raw/`. Run:",
        "",
        "```bash",
        ".venv_camel/bin/python scripts/eval_all_models_fixed.py",
        "```",
        "",
        "The official test snapshot is from the CATT project's benchmark fixture "
        f"at `{TASHKEELA_URL}`. It contains {len(official)} lines in this pinned "
        "repository state, not the 817k-line aggregate corpus used by unrelated "
        "text2tashkeel benchmarks; DER values must not be compared across those "
        "different corpora.",
        "",
    ]
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "diacritization_comparison.md").write_text("\n".join(lines), encoding="utf-8")


def main(args: argparse.Namespace) -> int:
    DATA.mkdir(parents=True, exist_ok=True)
    RAW_RESULTS.mkdir(parents=True, exist_ok=True)
    official_path = DATA / "tashkeela_test.txt"
    download_dataset(official_path)
    official_gold = read_lines(official_path)
    official_input = [re.sub(f"[{''.join(sorted(ARABIC_MARKS))}]", "", x) for x in official_gold]
    samer_path = ROOT / "attached_assets" / "samer_100_sentences_1789994666724.txt"
    manual_path = ROOT / "attached_assets" / "manual_check_30_1789994645863.txt"
    samer = read_lines(samer_path)
    manual_inputs = parse_manual_inputs(manual_path)
    if len(manual_inputs) != 30:
        raise RuntimeError(f"expected 30 manual inputs, found {len(manual_inputs)}")

    # Reuse the unmarked official text as model input; the SAMER and manual
    # inputs are already unmarked.
    inputs = {"official": official_input, "samer": samer, "manual": manual_inputs}
    outputs: dict[str, dict[str, list[str]]] = {m: {} for m in MODEL_LABELS}
    timings: dict[str, dict[str, float]] = {m: {} for m in MODEL_LABELS}
    for model in MODEL_LABELS:
        for name, lines in inputs.items():
            print(f"Running {MODEL_LABELS[model]} on {name} ({len(lines)} lines)...", flush=True)
            outputs[model][name], timings[model][name] = run_worker(model, name, lines)
    write_report(official_gold, samer, manual_inputs, outputs, timings)
    print(f"Wrote {RESULTS / 'diacritization_comparison.md'}")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--worker-model", choices=list(MODEL_LABELS))
    p.add_argument("--input")
    p.add_argument("--output")
    return p.parse_args()


if __name__ == "__main__":
    ns = parse_args()
    if ns.worker_model:
        raise SystemExit(worker(ns))
    raise SystemExit(main(ns))