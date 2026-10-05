"""Assemble bayan-simplification-corpus v1 from the generation checkpoint(s) and BAREC, split it, and write
the JSONL export.

Rows, every one tagged with pair_type:
  generated -- tier A/B winners (Gemma generator, Qwen judge), selected here from every logged candidate;
  protected -- scripture / Hanging Odes / verse-quoting BAREC rows, plus any source classify_protected.py
               labels classical_poetry / quran / hadith; output = input;
  short     -- rows of SHORT_MAX_WORDS words or fewer (distinct texts), output = input;
  identity  -- N_IDENTITY easy-band rows with the lowest mean AoA, domain- and length-matched to the
               generated set (the v0 method, assemble_provisional_export.py), output = input.
Protected and short rows are sampled to the training mix set by N_SHORT / PROTECTED_CAPS (see there).
All text is undiacritized (load_and_clean_barec strips it; the pipeline strips candidates). BAREC-test
rows, and any row whose text also occurs in BAREC-test, never enter (dataset_split.build_split).

Readability gate: readability_lead is the HARDEST-SENTENCE lead from rescore_sentencewise.py (source scored
whole, rewrite scored sentence by sentence, MCQs on the stem); readability_lead_whole keeps the lead of the
rewrite scored as one text, for reference. Meaning scores come from the pipeline's own judging plus
judge_pending.py for candidates that were never judged under the earlier whole-text floor.

    uv run python scripts/assemble_corpus_v1.py data/processed/v1_final/barec_hard_v1_checkpoint.jsonl \\
        --sentencewise data/processed/v1_final/barec_hard_v1_checkpoint.sentencewise.jsonl \\
        --judged data/processed/v1_final/barec_hard_v1_checkpoint.pending_judge.judged.jsonl \\
        --protected-labels data/processed/protected_labels.jsonl
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent))
from barec_simplification_pipeline import (
    BAREC_DIR, MIN_READABILITY_LEAD, PROCESSED_DIR, TIER_A_EQ_THRESHOLD, load_and_clean_barec,
)
from classify_protected import PROTECTED_KINDS
from dataset_split import build_split, normalize_text, verify_split
from check_leakage import check_leakage, is_substantive  # importable once dataset_split has set the path
from lexical_scorer import LexicalScorer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Training mix: every generated pair (the only rows that teach HOW to simplify) plus ~30% identity-type rows
# that teach WHEN NOT to. Copying is low-loss, so an identity-heavy mix pulls a seq2seq model toward
# under-simplifying; v1's generated pairs carry no near-copies (lead >= 2), which is why ~30% is affordable.
#   identity:  easy-band sentences, domain- and length-matched to the generated set, so "easy vs hard"
#              can't be read off length -- the most informative no-op signal, hence the largest share;
#   protected: scripture/poetry -- the model must recognize the style, so every kind is covered, with
#              verses/poetry found INSIDE other sources kept in full (the hardest case to recognize);
#   short:     headings and labels -- trivially recognizable by length, a few hundred suffice.
N_IDENTITY = 2900
N_SHORT = 750
PROTECTED_CAPS = {"Hadith": 250, "Bible": 150}  # everything else protected is kept in full
N_LENGTH_BINS = 5
SEED = 20260929
MIN_LEAK_WORDS = 5  # check_leakage.py's default: shorter matches are BAREC's own noise, not contamination
COLUMNS = [
    "ID", "original_text", "simplified_text", "pair_type", "source_level", "Source", "Domain",
    "acceptance_tier", "equivalence_score", "readability_lead", "readability_lead_whole",
    "source_camel_level", "hardest_sentence_level", "generator_model", "judge_model",
]
FLOATS = ("equivalence_score", "readability_lead", "readability_lead_whole", "source_camel_level", "hardest_sentence_level")


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def merge_candidates(row: dict, sentencewise: dict, judged: dict) -> list[dict]:
    """Every candidate of one source with its hardest-sentence lead and its meaning score (from the
    pipeline or from the later judge pass; None if never judged)."""
    whole = {c["simplified_text"]: c["readability_lead"] for c in (row.get("all_candidates") or []) + (row.get("below_lead") or [])}
    extra = judged.get(row["ID"], {})
    out = []
    for c in sentencewise.get(row["ID"], []):
        t = c["simplified_text"]
        eq = c["equivalence_score"] if c["equivalence_score"] is not None else extra.get(t)
        out.append({"simplified_text": t, "equivalence_score": eq, "readability_lead": c["readability_lead_sentence"],
                    "readability_lead_whole": whole.get(t), "source_camel_level": c["source_level_stem"],
                    "hardest_sentence_level": c["hardest_sentence_level"]})
    return out


def reselect(row: dict, cands: list[dict], eq_threshold: float, judge_model: str | None) -> dict | None:
    """The selection rule (gate -> tier -> lead) applied to every judged candidate with the final thresholds.
    None if no candidate is eligible."""
    eligible = [c for c in cands if c["equivalence_score"] is not None
                and c["equivalence_score"] >= eq_threshold and c["readability_lead"] >= MIN_READABILITY_LEAD]
    if not eligible:
        return None
    win = max(eligible, key=lambda c: (c["equivalence_score"] >= TIER_A_EQ_THRESHOLD, c["readability_lead"], c["equivalence_score"]))
    return {**{c: row.get(c) for c in COLUMNS}, **win, "judge_model": row.get("judge_model") or judge_model,
            "acceptance_tier": "A" if win["equivalence_score"] >= TIER_A_EQ_THRESHOLD else "B", "pair_type": "generated"}


def load_generated(paths: list[Path], sentencewise_path: Path, judged_paths: list[Path], eq_threshold: float) -> pl.DataFrame:
    rows = {}
    for path in paths:
        for r in _jsonl(path):
            rows[r["ID"]] = r  # shards never overlap; a resumed ID keeps its last record
    sentencewise = {r["ID"]: r["candidates"] for r in _jsonl(sentencewise_path)}
    judged, judge_model = {}, None
    for path in judged_paths:
        for r in _jsonl(path):
            judge_model = r.get("judge_model", judge_model)
            judged.setdefault(r["ID"], {}).update({c["simplified_text"]: c["equivalence_score"] for c in r["candidates"]})
    kept = [w for w in (reselect(r, merge_candidates(r, sentencewise, judged), eq_threshold, judge_model)
                        for r in rows.values()) if w]
    print(f"checkpoint: {len(rows)} sources, {len(kept)} accepted at eq >= {eq_threshold}, hardest-sentence lead >= "
          f"{MIN_READABILITY_LEAD} (A={sum(r['acceptance_tier'] == 'A' for r in kept)}, "
          f"B={sum(r['acceptance_tier'] == 'B' for r in kept)})")
    return pl.DataFrame([{c: r.get(c) for c in COLUMNS} for r in kept],
                        schema_overrides={c: pl.Float64 for c in FLOATS}, infer_schema_length=None)


def identity_rows(rows: pl.DataFrame, pair_type: str) -> pl.DataFrame:
    given = {"ID": pl.col("ID"), "original_text": pl.col("Sentence"), "simplified_text": pl.col("Sentence"),
             "pair_type": pl.lit(pair_type), "source_level": pl.col("Readability_Level_5"),
             "Source": pl.col("Source"), "Domain": pl.col("Domain")}
    return rows.select([
        given[c].alias(c) if c in given else pl.lit(None, dtype=pl.Float64 if c in FLOATS else pl.Utf8).alias(c)
        for c in COLUMNS
    ])


def aoa_identity(easy: pl.DataFrame, generated: pl.DataFrame, barec: pl.DataFrame) -> pl.DataFrame:
    """Lowest-AoA easy rows, drawn per domain and per generated-set length quintile (v0's method: a
    plain AoA sort collapses onto the shortest texts, since fewer words means lower mean AoA)."""
    scorer = LexicalScorer()
    pool = easy.with_columns(pl.col("Sentence").map_elements(lambda s: scorer.text(s)[0], return_dtype=pl.Float64).alias("mean_aoa"))
    gen_meta = barec.filter(pl.col("ID").is_in(generated["ID"].to_list())).select("Domain", "Word_Count")
    edges = np.quantile(gen_meta["Word_Count"].to_numpy(), np.linspace(0, 1, N_LENGTH_BINS + 1))
    edges[0], edges[-1] = -np.inf, np.inf
    bin_frac = np.histogram(gen_meta["Word_Count"].to_numpy(), bins=edges)[0] / gen_meta.height
    pool = pool.with_columns(pl.col("Word_Count").map_elements(
        lambda w: int(np.digitize(w, edges[1:-1])), return_dtype=pl.Int64).alias("len_bin"))
    picked = []
    for domain, count in gen_meta["Domain"].value_counts().iter_rows():
        target = N_IDENTITY * count / gen_meta.height
        for b in range(N_LENGTH_BINS):
            bucket = pool.filter((pl.col("Domain") == domain) & (pl.col("len_bin") == b)).sort("mean_aoa")
            picked.append(bucket.head(round(target * bin_frac[b])))
    return pl.concat(picked)


def sample_short(rows: pl.DataFrame) -> pl.DataFrame:
    """N_SHORT distinct short texts (BAREC repeats headings like «الدرس الأول» many times)."""
    distinct = rows.with_columns(pl.col("Sentence").map_elements(normalize_text, return_dtype=pl.Utf8).alias("_norm"))
    distinct = distinct.sort("ID").unique("_norm", keep="first", maintain_order=True).drop("_norm")
    return distinct.sample(n=min(N_SHORT, distinct.height), seed=SEED)


def sample_protected(rows: pl.DataFrame) -> pl.DataFrame:
    """All of every protected kind except the capped ones (PROTECTED_CAPS), which are sampled."""
    kind = (pl.when(pl.col("Source").is_in(["Old Testament", "New Testament"])).then(pl.lit("Bible"))
            .otherwise(pl.col("Source")))
    rows = rows.with_columns(kind.alias("_kind"))
    parts = []
    for (k,), group in rows.group_by("_kind"):
        cap = PROTECTED_CAPS.get(k)
        parts.append(group.sample(n=min(cap, group.height), seed=SEED) if cap else group)
    return pl.concat(parts).drop("_kind")


def drop_test_near_duplicates(corpus: pl.DataFrame) -> pl.DataFrame:
    """Remove every row whose source or target matches a BAREC-test sentence of 5+ words, exactly or as a
    near-duplicate (check_leakage.py's own definition). build_split already drops exact normalized
    matches; this also catches a rewrite or a sibling sentence that lands within 0.8 overlap of a test item."""
    test = pl.read_csv(BAREC_DIR / "test.csv", encoding="utf8-lossy")["Sentence"].to_list()
    texts = sorted(set(corpus["original_text"].to_list()) | set(corpus["simplified_text"].to_list()))
    exact, near = check_leakage(texts, test)
    leaked = {t for t, s in exact if is_substantive(t, s, MIN_LEAK_WORDS)}
    leaked |= {t for t, s, _ in near if is_substantive(t, s, MIN_LEAK_WORDS)}
    kept = corpus.filter(~pl.col("original_text").is_in(leaked) & ~pl.col("simplified_text").is_in(leaked))
    print(f"BAREC-test near-duplicates: {len(leaked)} texts, {corpus.height - kept.height} rows removed")
    return kept


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("checkpoints", nargs="+", type=Path)
    ap.add_argument("--out-dir", type=Path, default=PROCESSED_DIR / "corpus_v1")
    # 0.85 = tier A only. 0.75 was the calibrated floor (the lowest threshold at which the Qwen3.8 judge
    # accepts fewer planted additions and deletions than the v0 DeepSeek judge at 0.7), but an independent
    # audit of 1,156 generated pairs found tier B (0.75-0.85) lost nuance 2.8x as often as tier A
    # (37.6% vs 13.4%), so tier B is not shipped.
    ap.add_argument("--eq-threshold", type=float, default=TIER_A_EQ_THRESHOLD)
    ap.add_argument("--sentencewise", type=Path, required=True, help="rescore_sentencewise.py output")
    ap.add_argument("--judged", type=Path, nargs="*", default=[], help="judge_pending.py output(s)")
    ap.add_argument("--protected-labels", type=Path, help="classify_protected.py output")
    args = ap.parse_args()

    barec = load_and_clean_barec().filter(pl.col("barec_split") != "test")
    flagged = set()
    if args.protected_labels:
        flagged = {r["ID"] for r in _jsonl(args.protected_labels) if r["kind"] in PROTECTED_KINDS}
    hard_ids = set(barec.filter(pl.col("route") == "hard")["ID"].to_list()) - flagged
    # Only sources the current routing sends to the generator: a checkpoint row for a source that is now
    # protected (by Source, verse marker or the classifier) or short, or BAREC-test, never ships as a rewrite.
    generated = load_generated(args.checkpoints, args.sentencewise, args.judged, args.eq_threshold).filter(
        pl.col("ID").is_in(hard_ids)
    )
    print(f"classifier-protected sources removed from the generated set: {len(flagged)}")
    protected = identity_rows(sample_protected(
        barec.filter((pl.col("route") == "protected") | pl.col("ID").is_in(flagged))), "protected")
    short = identity_rows(sample_short(barec.filter(pl.col("route") == "short")), "short")
    identity = identity_rows(aoa_identity(barec.filter(pl.col("route") == "easy"), generated, barec), "identity")

    corpus = pl.concat([generated.select(COLUMNS), protected, short, identity], how="vertical_relaxed")
    corpus = drop_test_near_duplicates(corpus)
    print("assembled:", dict(corpus["pair_type"].value_counts().iter_rows()))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    assembled_path = args.out_dir / "corpus_v1_assembled.parquet"
    corpus.write_parquet(assembled_path)

    split = build_split(assembled_path, BAREC_DIR)
    verify_split(split)
    split.select("ID", "split", "stratum", "barec_split").write_csv(PROJECT_ROOT / "data" / "dataset_split.csv")
    split.select(COLUMNS + ["split"]).write_parquet(args.out_dir / "corpus_v1.parquet")
    for name in ("train", "dev", "test"):
        part = split.filter(pl.col("split") == name).select(COLUMNS).sort("ID")
        with open(args.out_dir / f"synthetic_{name}.jsonl", "w", encoding="utf-8") as f:
            for row in part.iter_rows(named=True):
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {part.height} rows to {args.out_dir / f'synthetic_{name}.jsonl'}")


if __name__ == "__main__":
    main()
