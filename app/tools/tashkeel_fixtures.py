"""Fixtures for DiacritizerTest: text2tashkeel's own Libtashkeel output on varied BayanBench texts (sources and app
outputs: digits, Latin words, punctuation, quotes, text that already carries tashkeel). The Kotlin port must match
every one exactly.
    python tools/tashkeel_fixtures.py BAYANBENCH_DATA PREDS_DIR > app/src/test/resources/tashkeel_fixtures.json"""
import json, random, sys
from pathlib import Path
import text2tashkeel
from text2tashkeel import Diacritizer

data, preds = Path(sys.argv[1]), Path(sys.argv[2])
rng = random.Random(61)
texts = [json.loads(l)["source"] for l in open(data / "items" / "dev.jsonl", encoding="utf-8")]
texts += [json.loads(l)["app"] for l in open(preds / "dev" / "model3-int8-b4-g2.jsonl", encoding="utf-8")]
rng.shuffle(texts)
picked = [t for t in texts if t.strip()][:300] + ["", "123", "Hello world", "قَالَ اللَّهُ تَعَالَى", "٢٠٢٤ عام جديد"]
d = Diacritizer("libtashkeel")
cases = [{"in": t, "out": d.diacritize(t)} for t in picked]
json.dump({"text2tashkeel": text2tashkeel.__version__, "model": "libtashkeel", "cases": cases}, sys.stdout, ensure_ascii=False)
print(len(cases), "cases", file=sys.stderr)
