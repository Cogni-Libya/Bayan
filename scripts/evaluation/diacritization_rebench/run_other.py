"""CATT encoder-only and Mishkal, run exactly as scripts/evaluation/benchmark_diacritization.py runs them."""
import json, re, sys, time
from pathlib import Path
H = Path(__file__).parent
MARKS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰ"
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
inputs = [re.sub(f"[{MARKS}]", "", x) for x in gold]
bench = json.load(open(H / "bayan_texts.json", encoding="utf-8"))
which = sys.argv[1]
if which == "catt":
    from catt_tashkeel import CATTEncoderOnly
    r = CATTEncoderOnly(); f = lambda xs: [x.replace("\n", " ") for x in r.do_tashkeel_batch(xs, batch_size=16, verbose=False)]
else:
    from mishkal.tashkeel import TashkeelClass
    r = TashkeelClass(); r.enabled_verbose = False; f = lambda xs: [r.tashkeel(x).replace("\n", " ") for x in xs]
f(["بسم الله"])
t = time.perf_counter(); out = f(inputs); secs = time.perf_counter() - t
json.dump({"model": which, "seconds": secs, "outputs": out, "bayan": f(bench)}, open(H / "out" / f"{which}.json", "w"), ensure_ascii=False)
print(which, f"{secs:.1f}s")
