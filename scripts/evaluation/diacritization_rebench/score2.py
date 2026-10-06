"""Convention-neutral view: the CATT/Tashkeela references are partly vowelled (no short vowel before a long one), so a
model that vowels fully is charged for correct marks. Here, with Sanad's alignment: DER on the positions the reference
marks (accuracy where it commits), and the share of reference-bare positions the model marks (fullness)."""
import json, sys, difflib
from pathlib import Path
H = Path(__file__).parent
sys.path.insert(0, str(H))
sys.path.insert(0, str(H.parents[0])); import benchmark_diacritization as sb   # the repo's own scoring code
gold = [l.rstrip("\n") for l in open(H / "CATT_data_gt.txt", encoding="utf-8") if l.strip()]
rows = []
for f in sorted((H / "out").glob("*.json")):
    r = json.load(open(f, encoding="utf-8"))
    mw = mt = bare = added = 0
    for ref, pred in zip(gold, r["outputs"]):
        R, P = sb.letter_units(ref), sb.letter_units(pred)
        sm = difflib.SequenceMatcher(a=[sb.canonical_letter(c) for c, _ in R], b=[sb.canonical_letter(c) for c, _ in P], autojunk=False)
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag not in ("equal", "replace"): 
                mt += sum(1 for k in range(i1, i2) if R[k][1]); mw += sum(1 for k in range(i1, i2) if R[k][1]); continue
            for a, b in zip(range(i1, i2), range(j1, j2)):
                if R[a][1]:
                    mt += 1; mw += R[a][1] != P[b][1]
                else:
                    bare += 1; added += bool(P[b][1])
    rows.append((100 * mw / mt, r["model"], 100 * added / bare))
print(f"{'model':38s} {'DER on marked':>14s} {'marks added where ref is bare':>30s}")
for a, n, b in sorted(rows): print(f"{n:38s} {a:14.2f} {b:30.1f}")
