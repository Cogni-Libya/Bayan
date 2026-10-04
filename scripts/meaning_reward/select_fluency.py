"""Choose the retrain checkpoint on fluency, with simplicity and meaning as guards (rule fixed before results).

  python select_fluency.py gen   --ckpts runs/X/ckpt --ref Congi-libya/bayan-arat5-v1 --dev v1/dev.jsonl --n 400 --out sel/   (transformers 4.x)
  python select_fluency.py pick  --run runs/X --out sel/                                                                    (after scoring)

gen: each checkpoint (and the reference model) rewrites the first --n generated rows of v1 dev; writes sel/pairs.jsonl
     ({"source", "prediction"}) and sel/map.json ({checkpoint: [[source, prediction], ...]}).
Score sel/pairs.jsonl with Gemma 4 31B in between: extra_questions.py (arabic) and bayanbench meaning (same).
pick: SARI per checkpoint from the trainer's log_history; rule: highest mean Gemma Arabic among checkpoints with
     SARI within 1 point of the best checkpoint and mean P(same) >= the reference model's on the same rows.
     Copies the chosen checkpoint's weights into RUN/model (tokenizer kept) and writes sel/choice.json.
"""
import argparse, glob, json, os, re, shutil, sys

ap = argparse.ArgumentParser()
ap.add_argument("mode", choices=["gen", "pick"])
ap.add_argument("--ckpts"); ap.add_argument("--ref"); ap.add_argument("--dev"); ap.add_argument("--n", type=int, default=400)
ap.add_argument("--run"); ap.add_argument("--out", required=True)
ap.add_argument("--prefix", default="بسط: ")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)

if a.mode == "gen":
    import torch
    from transformers import AutoModelForSeq2SeqLM, T5Tokenizer
    rows = [r for r in map(json.loads, open(a.dev, encoding="utf-8")) if r["pair_type"] == "generated"][:a.n]
    tok = T5Tokenizer.from_pretrained(a.ref, legacy=True)
    models = {"reference": a.ref, **{os.path.basename(c): c for c in sorted(glob.glob(f"{a.ckpts}/checkpoint-*"), key=lambda x: int(x.rsplit('-', 1)[1]))}}
    mp, pairs = {}, set()
    for name, path in models.items():
        m = AutoModelForSeq2SeqLM.from_pretrained(path).cuda().eval(); outs = []
        with torch.no_grad():
            for k in range(0, len(rows), 48):
                b = rows[k:k + 48]
                enc = tok([a.prefix + r["source"] for r in b], max_length=256, truncation=True, padding=True, return_tensors="pt").to("cuda")
                g = m.generate(**enc, max_length=256, num_beams=1, do_sample=False, no_repeat_ngram_size=4)
                outs += [t.strip() for t in tok.batch_decode(g, skip_special_tokens=True)]
        mp[name] = [[r["source"], o] for r, o in zip(rows, outs)]
        pairs |= {(r["source"], o) for r, o in zip(rows, outs)}
        print("generated", name, flush=True); del m; torch.cuda.empty_cache()
    json.dump(mp, open(f"{a.out}/map.json", "w"), ensure_ascii=False)
    with open(f"{a.out}/pairs.jsonl", "w", encoding="utf-8") as f:
        for s, o in sorted(pairs): f.write(json.dumps({"source": s, "prediction": o}, ensure_ascii=False) + "\n")
    print("SELECT_GEN_DONE", len(pairs), "pairs", flush=True)
else:
    DI = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
    nrm = lambda t: re.sub(r"\s+", " ", DI.sub("", t)).strip()
    ar = {(nrm(r["source"]), nrm(r["prediction"])): r["arabic"] for r in map(json.loads, open(f"{a.out}/extra.jsonl", encoding="utf-8"))}
    same = {(nrm(r["source"]), nrm(r["prediction"])): r["same"] for r in map(json.loads, open(f"{a.out}/meaning.jsonl", encoding="utf-8"))}
    mp = json.load(open(f"{a.out}/map.json", encoding="utf-8"))
    hist = json.load(open(f"{a.run}/log_history.json"))
    sari = {f"checkpoint-{h['step']}": h["eval_sari_changed"] for h in hist if "eval_sari_changed" in h}
    def score(name):
        A, S = [], []
        for s, o in mp[name]:
            k = (nrm(s), nrm(o))
            A.append(ar.get(k, ar.get((nrm(s), nrm(s)), 0.0)) if k in ar or nrm(o) == nrm(s) else 0.0)
            S.append(1.0 if nrm(o) == nrm(s) else same.get(k, 0.0))
        return sum(A) / len(A), sum(S) / len(S)
    table = {n: dict(zip(("arabic", "p_same"), score(n)), sari=sari.get(n)) for n in mp}
    ref_same = table["reference"]["p_same"]; best_sari = max(v["sari"] for n, v in table.items() if v["sari"] is not None)
    ok = [n for n, v in table.items() if n != "reference" and v["sari"] is not None and v["sari"] >= best_sari - 1.0 and v["p_same"] >= ref_same]
    choice = max(ok, key=lambda n: table[n]["arabic"]) if ok else None
    json.dump({"table": table, "reference_p_same": ref_same, "best_sari": best_sari, "eligible": ok, "choice": choice},
              open(f"{a.out}/choice.json", "w"), indent=1)
    print(json.dumps({"choice": choice, "table": table}, indent=1), flush=True)
    if choice:
        src = f"{a.run}/ckpt/{choice}"
        for f in glob.glob(f"{src}/*.safetensors") + glob.glob(f"{src}/config.json") + glob.glob(f"{src}/generation_config.json"):
            shutil.copy(f, f"{a.run}/model/")
        print("SELECTED", choice, flush=True)
    else:
        print("NO ELIGIBLE CHECKPOINT: keeping the SARI-best model", flush=True)
