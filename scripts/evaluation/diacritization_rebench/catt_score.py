"""Every out/*.json scored with CATT's official compute_der.py logic (pinned commit 8d53304), with and without case
endings."""
import json, sys
from pathlib import Path
H = Path(__file__).parent
sys.path.insert(0, str(H))
from tashkeel_tokenizer import TashkeelTokenizer
tok = TashkeelTokenizer()
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
print(f"{'model':38s} {'CATT DER':>9s} {'CATT WER':>9s} {'DER no-CE':>10s} {'WER no-CE':>10s}")
rows = []
for f in sorted((H / "out").glob("*.json")):
    r = json.load(open(f, encoding="utf-8")); res = []
    for ce in (True, False):
        dd = dl = wd = wl = 0
        for ref, hyp in zip(gold, r["outputs"]):
            ref, hyp = tok.clean_text(ref.strip()), tok.clean_text(hyp.strip())
            d = tok.compute_der(ref, hyp, case_ending=ce); w = tok.compute_wer(ref, hyp, case_ending=ce)
            dd += d["distance"]; dl += d["ref_length"]; wd += w["distance"]; wl += w["ref_length"]
        res += [100 * dd / dl, 100 * wd / wl]
    rows.append((res[0], r["model"], *res))
for _, name, a, b, c, d in sorted(rows):
    print(f"{name:38s} {a:9.2f} {b:9.2f} {c:10.2f} {d:10.2f}")
