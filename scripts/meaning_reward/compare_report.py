"""All-systems comparison: BayanBench (dev + test, Gemma 4 31B meaning), human ratings, reference-based SARI
(corpus v1 dev/test, SAMER test), Arabic-quality proxies, size and CPU speed. Writes report.json + report.md.

  python compare_report.py --cfg compare_cfg.json --out compare/report

compare_cfg.json: {"bench_data": dir, "ratings": jsonl, "barec_train": csv, "scores": [jsonl, ...],
                   "bench": {"dev": {system: preds}, "test": {...}}, "gen": dir, "latency": json,
                   "refsets": {set: jsonl}, "models": [names in gen/], "history": {name: {metric: value}}}
"""
import argparse, csv, json, re, subprocess, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "training" / "model2"))
from sari import sari_sentence  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("--cfg", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--skip-bench", action="store_true")
a = ap.parse_args()
cfg = json.load(open(a.cfg, encoding="utf-8")); out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
R = {"bench": {}, "contradiction": {}, "human": {}, "refsets": {}, "quality": {}, "latency": {}, "history": cfg.get("history", {})}
DI = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
SETS = ["core", "outside", "written"]

# ---------- 1) BayanBench scorecards ----------
KEYS = [("meaning", "P(same meaning)", "p_same"), ("meaning", "meaning kept", "meaning_kept"),
        ("simpler", "longest clause: words shorter", "clause_shorter"), ("simpler", "reading level: levels lower", "level_lower"),
        ("checks", "numbers kept", "numbers_kept"), ("checks", "no house-rule break", "house_rules"),
        ("behaviour", "C: easy text left unchanged", "easy_unchanged"), ("behaviour", "F: letters unchanged", "protected_letters"),
        ("behaviour", "E1: end mark kept", "end_mark"), ("flags", "negation changed", "neg_changed"),
        ("flags", "limit changed", "limit_changed"), ("flags", "condition changed", "cond_changed")]
if not a.skip_bench:
    sc_args = sum((["--meaning-scores", s] for s in cfg["scores"]), [])
    for split, systems in cfg["bench"].items():
        for name, path in systems.items():
            j = out / f"bench_{split}__{name}.json"
            if not j.exists():
                cmd = [sys.executable, "-m", "bayanbench.cli", "score", "--data", cfg["bench_data"], "--split", split, path,
                       "--no-samer", "--meaning-threshold", "0.5", "--joint", "--simpler-min", "2,0.5", "--json", str(j)] + sc_args
                for s in SETS: cmd += ["--set", s]
                r = subprocess.run(cmd, capture_output=True, text=True)
                if r.returncode: print("score failed", split, name, r.stderr[-500:], flush=True); continue
            res = json.load(open(j)); R["bench"].setdefault(split, {})[name] = {}
            for s in SETS:
                blk = res["sets"].get(s, {}); row = {}
                for b, m, k in KEYS:
                    e = blk.get(b, {}).get(m)
                    if e: row[k] = (e.get("mean") or e.get("rate"))[0]
                for b in blk.values():
                    if isinstance(b, dict):
                        for m, e in b.items():
                            if "and simpler" in m and isinstance(e, dict): row["joint"] = (e.get("rate") or e.get("mean"))[0]
                R["bench"][split][name][s] = row
            print("bench", split, name, flush=True)

# contradiction rate among changed outputs (31B P(contradict) >= 0.5)
sc = {}
for f in cfg["scores"] + [str(Path(cfg["bench_data"]) / "meaning" / "gemma-4-31b_dev.jsonl")]:
    for l in open(f, encoding="utf-8"):
        r = json.loads(l); sc[(r["source"], r["prediction"])] = r
for split, systems in cfg["bench"].items():
    items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(cfg["bench_data"]) / "items" / f"{split}.jsonl", encoding="utf-8")}
    for name, path in systems.items():
        n = c = 0
        for l in open(path, encoding="utf-8"):
            p = json.loads(l); it = items[p["id"]]
            if (it.get("set") or "core") not in ("core", "outside"): continue
            o = p.get("output") or p.get("prediction"); s = it["source"]
            if DI.sub("", o).strip() == DI.sub("", s).strip(): continue
            r = sc.get((s, o))
            if r: n += 1; c += r["contradict"] >= 0.5
        R["contradiction"].setdefault(split, {})[name] = {"changed_scored": n, "contradict_rate": c / max(1, n)}

# ---------- 2) human ratings ----------
rows = [json.loads(l) for l in open(cfg["ratings"], encoding="utf-8")]
by = collections.defaultdict(list)
for r in rows:
    if r["kind"] == "single": by[r["system"]].append(r)
def auc(pos, neg):
    if not pos or not neg: return None
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))
for name, rs in by.items():
    votes = lambda k: [v[k] for r in rs for v in r["ratings"].values() if k in v]
    m, ar, e = votes("m"), votes("a"), votes("e")
    R["human"][name] = {"items": len(rs), "ratings": len(m),
                        "meaning_same": m.count("same") / len(m), "meaning_major": m.count("major") / len(m),
                        "arabic_ok": ar.count("ok") / len(ar), "arabic_major": ar.count("major") / len(ar),
                        "easier": e.count("easier") / len(e), "harder": e.count("harder") / len(e)}
allr = [r for r in rows if r["kind"] == "single" and r.get("meaning_majority") in ("same", "minor", "major")]
R["human"]["_31b_auc_same_vs_not"] = auc([r["p_same"] for r in allr if r["meaning_majority"] == "same"],
                                         [r["p_same"] for r in allr if r["meaning_majority"] != "same"])
R["human"]["_31b_auc_major_vs_rest"] = auc([1 - r["p_same"] for r in allr if r["meaning_majority"] == "major"],
                                           [1 - r["p_same"] for r in allr if r["meaning_majority"] != "major"])
pairs = [r for r in rows if r["kind"] == "pair"]
pw = collections.Counter()
for r in pairs:
    for v in r["ratings"].values():
        if "p" in v: pw[(r["a"], r["b"], v["p"])] += 1
R["human"]["_pairwise"] = {f"{x} vs {y}": {"a": pw[(x, y, "a")], "b": pw[(x, y, "b")], "same": pw[(x, y, "same")]}
                           for x, y in {(r["a"], r["b"]) for r in pairs}}


# ---------- 2b) extra 31B scores (arabic, simpler, coherent), per system, and against the human labels ----------
R["extra"] = {}
if cfg.get("extra_scores") and Path(cfg["extra_scores"]).exists():
    ex = {}
    for l in open(cfg["extra_scores"], encoding="utf-8"):
        r = json.loads(l); ex[(r["source"], r["prediction"])] = r
    for split, systems in cfg["bench"].items():
        items = {json.loads(l)["id"]: json.loads(l) for l in open(Path(cfg["bench_data"]) / "items" / f"{split}.jsonl", encoding="utf-8")}
        for name, path in systems.items():
            vals = collections.defaultdict(list)
            for l in open(path, encoding="utf-8"):
                p = json.loads(l); it = items[p["id"]]
                if (it.get("set") or "core") not in ("core", "outside") or it.get("track") == "F": continue
                s = it["source"]; o = p.get("output") or p.get("prediction")
                r = ex.get((s, o)) or (ex.get((s, s)) if DI.sub("", o).strip() == DI.sub("", s).strip() else None)
                if not r: continue
                for k in ("arabic", "simpler", "coherent"): vals[k].append(r[k])
            if vals:
                R["extra"].setdefault(split, {})[name] = {k: sum(v) / len(v) for k, v in vals.items()} | \
                    {k + "_ok": sum(x >= 0.5 for x in v) / len(v) for k, v in vals.items()} | {"n": len(vals["arabic"])}
    def maj(r, k):
        v = [x[k] for x in r["ratings"].values() if k in x]; c = collections.Counter(v).most_common()
        return c[0][0] if c and (len(c) == 1 or c[0][1] > c[1][1]) else None
    sing = [r for r in rows if r["kind"] == "single"]
    val = {}
    for k, good, hk in (("arabic", "ok", "a"), ("simpler", "easier", "e")):
        pos, neg = [], []
        for r in sing:
            m = maj(r, hk); e = ex.get((r["source"], r["output"])) or ex.get((r["source"], r["source"]))
            if m is None or not e: continue
            (pos if m == good else neg).append(e[k])
        val[k] = {"auc_vs_human_majority": auc(pos, neg), "n_pos": len(pos), "n_neg": len(neg)}
    R["extra"]["_validation"] = val

# ---------- 3) reference-based sets + 4) Arabic-quality proxies ----------
def words(t): return re.findall(r"[ء-ي]+", DI.sub("", t))
def norm(w): return re.sub("[أإآ]", "ا", w).replace("ى", "ي").replace("ة", "ه")
lex = collections.Counter()
for row in csv.DictReader(open(cfg["barec_train"], encoding="utf-8-sig")):
    for w in words(row["Sentence"]): lex[norm(w)] += 1
L = {w for w, c in lex.items() if c >= 2}
KEEP = {"identity", "protected", "short"}
for sname, spath in cfg["refsets"].items():
    rows_ = [json.loads(l) for l in open(spath, encoding="utf-8")]
    for name in ["copy"] + cfg["models"]:
        if name == "copy": pred = {r["id"]: r["source"] for r in rows_}
        else:
            f = Path(cfg["gen"]) / f"{sname}__{name}.jsonl"
            if not f.exists(): continue
            pred = {str(json.loads(l)["id"]): json.loads(l)["prediction"] for l in open(f, encoding="utf-8")}
            pred = {r["id"]: pred.get(str(r["id"]), "") for r in rows_}
        refs = lambda r: r.get("refs") or [r["target"]]
        ch = [r for r in rows_ if r["source"] != r["target"] and r.get("pair_type", "generated") not in KEEP]
        kp = [r for r in rows_ if r.get("pair_type") in KEEP]
        same = lambda r: DI.sub("", pred[r["id"]]).strip() == DI.sub("", r["source"]).strip()
        row = {"sari_changed": sum(sari_sentence(r["source"], pred[r["id"]], refs(r)) for r in ch) / max(1, len(ch)),
               "sari_all": sum(sari_sentence(r["source"], pred[r["id"]], refs(r)) for r in rows_) / len(rows_),
               "copy_changed": sum(map(same, ch)) / max(1, len(ch)), "n_changed": len(ch)}
        if kp: row["keep_unchanged"] = sum(map(same, kp)) / len(kp)
        R["refsets"].setdefault(sname, {})[name] = row
        if name != "copy":
            nw = tot = rep = nch = 0
            for r in rows_:
                o, s = pred[r["id"]], r["source"]
                if same(r): continue
                nch += 1; sw = {norm(w) for w in words(s)}; ow = [norm(w) for w in words(o)]
                new = [w for w in ow if w not in sw]; tot += len(new); nw += sum(w not in L for w in new)
                rep += any(ow[i] == ow[i + 1] for i in range(len(ow) - 1)) or any(c >= 2 for c in collections.Counter(zip(ow, ow[1:], ow[2:])).values())
            R["quality"].setdefault(sname, {})[name] = {"new_words_not_in_barec": nw / max(1, tot), "repeated_word_or_3gram": rep / max(1, nch)}
        print("refset", sname, name, flush=True)

# ---------- 5) size and CPU speed ----------
if Path(cfg["latency"]).exists(): R["latency"] = json.load(open(cfg["latency"]))
json.dump(R, open(out / "report.json", "w"), ensure_ascii=False, indent=1)
print("REPORT_JSON_DONE", flush=True)

# ---------- markdown ----------
f = lambda x, p=False: "–" if x is None else (f"{100 * x:.1f}%" if p else f"{x:.2f}")
md = ["# All-systems comparison", ""]
for split in ("dev", "test"):
    if split not in R["bench"]: continue
    for st in ("core", "outside"):
        md += [f"## BayanBench {split}, {st} (Gemma 4 31B meaning; meaning kept at P(same) >= 0.5, provisional)", "",
               "| system | P(same) | meaning kept | joint | clause shorter | level lower | numbers kept | easy unchanged | protected letters | neg / limit / cond changed | contradict (31B) | arabic (31B) | simpler (31B) | coherent (31B) |",
               "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for name, sets in R["bench"][split].items():
            b = sets.get(st, {}); c = R["contradiction"].get(split, {}).get(name, {}); e = R["extra"].get(split, {}).get(name, {})
            md.append(f"| {name} | {f(b.get('p_same'))} | {f(b.get('meaning_kept') and b['meaning_kept'] / 100, True)} | {f(b.get('joint') and b['joint'] / 100, True)} | "
                      f"{f(b.get('clause_shorter'))} | {f(b.get('level_lower'))} | {f(b.get('numbers_kept') and b['numbers_kept'] / 100, True)} | "
                      f"{f(b.get('easy_unchanged') and b['easy_unchanged'] / 100, True)} | {f(b.get('protected_letters') and b['protected_letters'] / 100, True)} | "
                      f"{f(b.get('neg_changed'))} / {f(b.get('limit_changed'))} / {f(b.get('cond_changed'))} | "
                      f"{f(c.get('contradict_rate'), True) if st == 'core' else ''} | {f(e.get('arabic')) if st == 'core' else ''} | {f(e.get('simpler')) if st == 'core' else ''} | {f(e.get('coherent')) if st == 'core' else ''} |")
        md.append("")
md += ["## Human ratings (BayanBench dev, rating round)", "", "| system | items | meaning same | meaning major | Arabic ok | Arabic major | easier | harder |", "|---|---|---|---|---|---|---|---|"]
for name, h in R["human"].items():
    if name.startswith("_"): continue
    md.append(f"| {name} | {h['items']} | {f(h['meaning_same'], True)} | {f(h['meaning_major'], True)} | {f(h['arabic_ok'], True)} | {f(h['arabic_major'], True)} | {f(h['easier'], True)} | {f(h['harder'], True)} |")
md += ["", f"Gemma 4 31B P(same) vs human majority: AUC {f(R['human']['_31b_auc_same_vs_not'])} (same vs not), {f(R['human']['_31b_auc_major_vs_rest'])} (major vs rest).", ""]
if "_validation" in R["extra"]:
    v = R["extra"]["_validation"]
    md += [f"Extra 31B scores vs human majority (rater agreement is low: alpha 0.17 Arabic, 0.19 ease): arabic AUC {f(v['arabic']['auc_vs_human_majority'])}, simpler AUC {f(v['simpler']['auc_vs_human_majority'])}.", ""]
for sname, t in R["refsets"].items():
    md += [f"## {sname} (SARI against {'human L3 + L4' if 'samer' in sname else 'corpus v1 targets'})", "",
           "| system | SARI changed rows | SARI all | copies changed rows | keep-rows unchanged | new words not in BAREC | repeated word / 3-gram |", "|---|---|---|---|---|---|---|"]
    for name, r in t.items():
        q = R["quality"].get(sname, {}).get(name, {})
        md.append(f"| {name} | {r['sari_changed']:.1f} | {r['sari_all']:.1f} | {f(r['copy_changed'], True)} | {f(r.get('keep_unchanged'), True)} | {f(q.get('new_words_not_in_barec'), True)} | {f(q.get('repeated_word_or_3gram'), True)} |")
    md.append("")
if R["latency"]:
    md += ["## Size and CPU speed (fp32, batch 1, 4 threads, 100 v1 test sentences)", "", "| model | parameters | fp32 size | seconds per sentence |", "|---|---|---|---|"]
    for name, l in R["latency"].items(): md.append(f"| {name} | {l['params_M']}M | {l['fp32_MB']} MB | {l['cpu_s_per_sentence']:.2f} |")
open(out / "report.md", "w", encoding="utf-8").write("\n".join(md) + "\n")
print("REPORT_MD_DONE", flush=True)
