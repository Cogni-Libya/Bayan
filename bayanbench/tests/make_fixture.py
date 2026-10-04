"""Build a tiny benchmark data folder for the tests (no private data needed)."""
import hashlib
import json
from pathlib import Path

ITEMS = [
    {"id": "A1-x1", "doc": "d1", "domain": "encyclopedia", "track": "A1", "source": "زار الوفد المدينة في عام 2020 ولم يلتق بالوزير."},
    {"id": "B-x2", "doc": "d2", "domain": "literature", "track": "B",
     "source": "كان الرجل الذي يسكن في البيت الكبير القريب من النهر يخرج كل صباح باكرا ليسقي الأشجار التي زرعها أبوه قبل سنوات طويلة."},
    {"id": "C-x3", "doc": "d3", "domain": "children", "track": "C", "source": "ذهب الولد إلى المدرسة."},
    {"id": "F-x4", "doc": "d4", "domain": "scripture", "track": "F", "source": "بِسْمِ اللَّهِ الرَّحْمَنِ الرَّحِيمِ الحمد لله رب العالمين"},
    {"id": "A3-x5", "doc": "d5", "domain": "outside-health", "set": "outside", "track": "A3",
     "source": "يؤخذ الدواء مرتين يوميا بعد الأكل ولا يجوز مضغ القرص."},
]


def build(d):
    d = Path(d)
    (d / "items").mkdir(parents=True, exist_ok=True)
    for sp in ("dev", "test"):
        with open(d / "items" / f"{sp}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for it in ITEMS:
                f.write(json.dumps(it, ensure_ascii=False) + "\n")
    (d / "verdicts").mkdir(exist_ok=True)
    return d


def write_manifest(d, accepted=("t:judge|v2",)):
    d = Path(d)
    files = {str(p.relative_to(d)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
             for p in d.rglob("*") if p.is_file() and p.name != "manifest.json"}
    (d / "manifest.json").write_text(json.dumps({"version": "test", "files": files, "accepted_judges": list(accepted),
                                                 "judge_acceptance": {}}), encoding="utf-8")
