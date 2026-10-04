"""Score every out/*.json with the repo's own benchmark functions (scripts/evaluation/benchmark_diacritization.py)."""
import json, re, sys
from pathlib import Path
H = Path(__file__).parent
sys.path.insert(0, str(H))
sys.path.insert(0, str(H.parents[0])); import benchmark_diacritization as sb   # the repo's own scoring code
MARKS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰ"
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
bench = json.load(open(H / "bayan_texts.json", encoding="utf-8"))
rows = []
for f in sorted((H / "out").glob("*.json")):
    r = json.load(open(f, encoding="utf-8"))
    m = sb.sentence_metrics(gold, r["outputs"])
    changed = sum(sb.exact_base_signature(a) != sb.exact_base_signature(b) for a, b in zip(bench, r.get("bayan", bench)))
    rows.append((m["der"], r["model"], m["der_nc"], m["wer"], m["base_corrupt_sentences"], changed, len(r.get("bayan", [])), len(gold) / r["seconds"]))
print(f"{'model':38s} {'DER':>6s} {'DER-nc':>7s} {'WER':>6s} {'letters chg CATT':>16s} {'letters chg Bayan':>17s} {'sent/s':>7s}")
for der, name, dnc, wer, cc, bc, bn, sps in sorted(rows):
    print(f"{name:38s} {der:6.2f} {dnc:7.2f} {wer:6.2f} {cc:>16d} {f'{bc}/{bn}':>17s} {sps:7.1f}")
