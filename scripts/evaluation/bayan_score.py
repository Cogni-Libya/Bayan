#!/usr/bin/env python3
"""
Bayan Score: the share of sentences whose output is easier for a dyslexic reader AND says the same thing.
Reference-free, so it runs on any prediction file, BAREC included.

    CAMELTOOLS_DATA=~/camel_data uv run --no-project --python 3.11 --with camel-tools --with torch \
        --with "transformers==4.57.6" --with sentence-transformers --with sentencepiece --with protobuf \
        --with tiktoken python scripts/evaluation/bayan_score.py --barec-train data/raw/barec/train.csv \
        pred_barec_S0.jsonl pred_barec_S1.jsonl pred_barec_S2.jsonl pred_barec_S3.jsonl
    (once: CAMELTOOLS_DATA=~/camel_data uv run --no-project --python 3.11 --with camel-tools \
        camel_data -i disambig-mle-calima-msa-r13)

A row PASSES when its output is both:

EASIER
  target       every output sentence has <= 15 words, and CAMeL Lab's BAREC readability model (trained on 69k
               human-graded sentences) puts every output sentence at level 10.15 or easier: as easy as a typical
               sentence that SAMER's human editors simplified to L3
  well-formed  every output sentence reads as complete: AraGPT2 gives its closing full stop a log-probability
               >= -4.96 (95% of human L3 sentences pass; a sentence chopped mid-phrase usually fails)
  lighter      the dyslexia load does not rise. Load = the shares of rare, long, morphologically dense and
               ambiguous words, each a text feature that affects dyslexic readers specifically:
                 rare, long   Rello et al. 2013: frequent and short words helped readers with dyslexia, not controls
                 dense        Arabic morphological density hurt comprehension of children with reading
                              disabilities, not typical readers (Dyslexia, 2024, doi:10.1002/dys.1761). Counted with CAMeL Tools
                              (attached morphemes per word, D3 tokenization)
                 ambiguous    words with 2+ readings without tashkeel (dyslexia_features.py)
SAME MEANING
  LaBSE similarity to the source >= 0.733; at least 87.5% of the source's word count kept; every number kept;
  the same count of negation words; the source entails every output sentence (mDeBERTa-XNLI p >= 0.028) and
  contradicts none (p <= 0.718)

A source that already meets the target passes when its output keeps meeting it, so copying an easy sentence is
fine. The headline number is the pass rate on HARD rows: sources that do not meet the target yet.
Every threshold was set on human rewrites (SAMER dev, L5 -> L3: the 5th / 95th percentile), never on a model's
output. Validation against human judgements is in docs/bayan_score.md.
"""

import argparse
import json
import re
import statistics as st
import sys
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoModelForSequenceClassification, AutoTokenizer

sys.path.insert(0, str(Path(__file__).parent))
import dyslexia_features as DF  # noqa: E402

TH = {"MAX_WORDS": 15, "MAX_LEVEL": 10.15, "MIN_END": -4.96, "MIN_LABSE": 0.733, "MIN_KEEP": 0.875,
      "MIN_NLI": 0.028, "MAX_CONTRA": 0.718}
DIAC = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
NON_LETTER = re.compile(r"[^ء-ي\s]")
SENT = re.compile(r"[.!?؟;؛\n]+")
NUM = re.compile(r"[0-9٠-٩]+")
NEG = {"لا", "لم", "لن", "ليس", "ليست", "ليسوا", "لست", "غير", "دون", "بدون", "ولا", "ولم", "ولن", "وليس", "فلا", "فلم"}
DEV = "cuda" if torch.cuda.is_available() else "cpu"


def strip(t: str) -> str:
    return DIAC.sub("", str(t))


def words(t: str) -> list[str]:
    return NON_LETTER.sub(" ", strip(t)).split()


def sentences(t: str) -> list[str]:
    return [s.strip() for s in SENT.split(strip(t)) if words(s)]


class Models:
    def __init__(self, barec_train: Path):
        from camel_tools.disambig.mle import MLEDisambiguator
        from camel_tools.tokenizers.morphological import MorphologicalTokenizer
        from sentence_transformers import SentenceTransformer

        self.rt = AutoTokenizer.from_pretrained("CAMeL-Lab/readability-arabertv02-word-CE")
        self.rm = AutoModelForSequenceClassification.from_pretrained("CAMeL-Lab/readability-arabertv02-word-CE")
        self.labse = SentenceTransformer("sentence-transformers/LaBSE", device=DEV)
        nli = "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7"
        self.nt, self.nm = AutoTokenizer.from_pretrained(nli), AutoModelForSequenceClassification.from_pretrained(nli)
        self.ent = self.nm.config.label2id.get("entailment", 0)
        self.con = self.nm.config.label2id.get("contradiction", 2)
        self.gt = AutoTokenizer.from_pretrained("aubmindlab/aragpt2-base")
        self.gm = AutoModelForCausalLM.from_pretrained("aubmindlab/aragpt2-base")
        self.dot = self.gt(" .", add_special_tokens=False).input_ids[-1]
        for m in (self.rm, self.nm, self.gm):
            m.to(DEV).eval()
            if DEV == "cuda":
                m.half()
        if DEV == "cuda":
            self.labse.half()
        self.morph = MorphologicalTokenizer(MLEDisambiguator.pretrained(), scheme="d3tok", split=True)
        self.top, self.amb = DF.lexicons(barec_train)

    @torch.no_grad()
    def level(self, texts: list[str], bs: int = 64) -> list[float]:
        """expected BAREC level (1..19), as score.py computes it"""
        out = []
        for i in range(0, len(texts), bs):
            enc = self.rt([strip(t) for t in texts[i:i + bs]], truncation=True, padding=True,
                          return_tensors="pt").to(DEV)
            p = torch.softmax(self.rm(**enc).logits.float(), -1)
            out += (p * torch.arange(1, p.shape[1] + 1, device=DEV)).sum(-1).tolist()
        return out

    @torch.no_grad()
    def nli(self, prem: list[str], hyp: list[str], bs: int = 64) -> tuple[list[float], list[float]]:
        ent, con = [], []
        for i in range(0, len(prem), bs):
            enc = self.nt(prem[i:i + bs], hyp[i:i + bs], truncation=True, max_length=320, padding=True,
                          return_tensors="pt").to(DEV)
            p = torch.softmax(self.nm(**enc).logits.float(), -1)
            ent += p[:, self.ent].tolist()
            con += p[:, self.con].tolist()
        return ent, con

    @torch.no_grad()
    def end_lp(self, texts: list[str]) -> list[float]:
        """log P('.' | sentence) under AraGPT2"""
        out = []
        for s in texts:
            s = s.strip().rstrip(".؟!،؛:") or "-"
            ids = self.gt(s, return_tensors="pt", truncation=True, max_length=200).input_ids.to(DEV)
            full = torch.cat([ids, torch.tensor([[self.dot]], device=DEV)], 1)
            out.append(torch.log_softmax(self.gm(full).logits[0, -2].float(), -1)[self.dot].item())
        return out

    def load(self, t: str) -> dict | None:
        w = words(t)
        if not w:
            return None
        clitics = sum(1 for x in self.morph.tokenize(w) if x.endswith("+") or x.startswith("+"))
        return {"rare": sum(x not in self.top for x in w) / len(w), "long": sum(len(x) >= 7 for x in w) / len(w),
                "dense": clitics / len(w), "ambig": sum(x in self.amb for x in w) / len(w)}


def score_rows(m: Models, rows: list[dict]) -> list[dict]:
    """per row: easier, faithful, hard (source does not meet the target), and why it failed"""
    out_s = [sentences(r["prediction"]) or [strip(r["prediction"]) or "-"] for r in rows]
    src_s = [sentences(r["source"]) or [strip(r["source"]) or "-"] for r in rows]
    flat = [(k, s) for k, ss in enumerate(out_s) for s in ss]
    sflat = [(k, s) for k, ss in enumerate(src_s) for s in ss]
    lv = m.level([s for _, s in flat])
    end = m.end_lp([s for _, s in flat])
    ent, con = m.nli([strip(rows[k]["source"]) for k, _ in flat], [s for _, s in flat])
    slv = m.level([s for _, s in sflat])
    ea = m.labse.encode([strip(r["source"]) for r in rows], batch_size=64, normalize_embeddings=True)
    eb = m.labse.encode([strip(r["prediction"]) or "-" for r in rows], batch_size=64, normalize_embeddings=True)
    per = [{"lv": [], "end": [], "ent": [], "con": [], "slv": []} for _ in rows]
    for (k, _), a, b, c, d in zip(flat, lv, end, ent, con):
        per[k]["lv"].append(a); per[k]["end"].append(b); per[k]["ent"].append(c); per[k]["con"].append(d)
    for (k, _), a in zip(sflat, slv):
        per[k]["slv"].append(a)
    res = []
    for r, p, os_, ss, x, y in zip(rows, per, out_s, src_s, ea, eb):
        src, out = r["source"], r["prediction"]
        hard = not (max(len(words(s)) for s in ss) <= TH["MAX_WORDS"] and max(p["slv"]) <= TH["MAX_LEVEL"])
        ls, lo = m.load(src), m.load(out)
        ew, fw = [], []                                  # reasons it is not easier / not faithful
        if max(len(words(s)) for s in os_) > TH["MAX_WORDS"]: ew.append("long sentence")
        if max(p["lv"]) > TH["MAX_LEVEL"]: ew.append("reading level")
        if min(p["end"]) < TH["MIN_END"]: ew.append("fragment")
        if not (ls and lo and sum(lo.values()) <= sum(ls.values()) + 1e-9): ew.append("heavier load")
        if float((x * y).sum()) < TH["MIN_LABSE"]: fw.append("meaning drift")
        if len(words(out)) < TH["MIN_KEEP"] * len(words(src)): fw.append("content dropped")
        if not set(NUM.findall(strip(src))) <= set(NUM.findall(strip(out))): fw.append("number lost")
        if sum(w in NEG for w in words(src)) != sum(w in NEG for w in words(out)): fw.append("negation changed")
        if min(p["ent"]) < TH["MIN_NLI"] or max(p["con"]) > TH["MAX_CONTRA"]: fw.append("not entailed")
        easier, faithful, why = not ew, not fw, ew + fw
        res.append({"id": r.get("id"), "hard": hard, "easier": easier, "faithful": faithful,
                    "pass": easier and faithful, "why": why, "load_src": ls, "load_out": lo})
    return res


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--barec-train", required=True, type=Path)
    p.add_argument("--details", type=Path, help="optional: write per-row results (JSONL) to this directory")
    p.add_argument("predictions", nargs="+", type=Path)
    args = p.parse_args()
    m = Models(args.barec_train)
    print(f"{'file':28}{'rows':>6}{'hard':>6}{'SCORE (hard)':>14}{'score (all)':>13}{'easier':>8}{'faithful':>10}"
          "   top failure reasons on hard rows")
    for path in args.predictions:
        with open(path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
        res = score_rows(m, rows)
        hard = [r for r in res if r["hard"]]
        pct = lambda xs, k: 100 * st.mean(x[k] for x in xs) if xs else float("nan")
        reasons: dict[str, int] = {}
        for r in hard:
            for w in r["why"]:
                reasons[w] = reasons.get(w, 0) + 1
        top = ", ".join(f"{k} {100 * v / max(1, len(hard)):.0f}%" for k, v in sorted(reasons.items(), key=lambda kv: -kv[1])[:4])
        print(f"{path.name:28}{len(res):>6}{len(hard):>6}{pct(hard, 'pass'):>14.1f}{pct(res, 'pass'):>13.1f}"
              f"{pct(hard, 'easier'):>8.1f}{pct(hard, 'faithful'):>10.1f}   {top}")
        if args.details:
            args.details.mkdir(parents=True, exist_ok=True)
            with open(args.details / f"bayan_{path.stem}.jsonl", "w", encoding="utf-8") as f:
                for r in res:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
