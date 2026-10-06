"""Run text2tashkeel models on the 743-sentence CATT/Tashkeela fixture and on 300 BayanBench texts (letter check).
    TT_ORT_THREADS=1 python run_t2t.py MODEL [MODEL ...]"""
import json, re, sys, time
from pathlib import Path
from text2tashkeel import Diacritizer
H = Path(__file__).parent
MARKS = "".join(chr(c) for c in range(0x064B, 0x0653)) + "ٰ"
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
inputs = [re.sub(f"[{MARKS}]", "", x) for x in gold]
bench = json.load(open(H / "bayan_texts.json", encoding="utf-8"))
for name in sys.argv[1:]:
    d = Diacritizer(name); d.diacritize("بسم الله")          # load + warm-up, not timed
    t = time.perf_counter(); out = [d.diacritize(x).replace("\n", " ") for x in inputs]; secs = time.perf_counter() - t
    bout = [d.diacritize(x) for x in bench]
    json.dump({"model": name, "seconds": secs, "outputs": out, "bayan": bout}, open(H / "out" / f"{name}.json", "w"), ensure_ascii=False)
    print(name, f"{secs:.1f}s", flush=True)
