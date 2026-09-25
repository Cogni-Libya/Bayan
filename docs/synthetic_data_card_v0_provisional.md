---
language:
- ar
license: cc-by-sa-4.0
license_name: cc-by-sa-4.0
license_link: https://creativecommons.org/licenses/by-sa/4.0/
task_categories:
- text-generation
tags:
- arabic
- text-simplification
- dyslexia
- synthetic-data
- barec
size_categories:
- 10K<n<100K
pretty_name: Bayan DeepSeek Synthetic Simplification Corpus
---

# Synthetic simplification data card — v0-provisional

**Status: provisional.** This export applies the readability-lead quarantine (see below) but has
not yet incorporated the morning relabel this thread's expert consultation called for (the four
strata: `lead<=0`, near-margin `d_logit-TAU`, tier A/B boundary, spike-in retest). Numbers here are
the honest current state, not a final release. Re-run `scripts/dataset_split.py` once the relabel
lands; the split mechanism itself does not need to change, only which rows are eligible going in.

Closes the DeepSeek-pipeline portion of issue #8 (Marwan's pipeline dropped from scope, agreed
directly with him — see issue #12, which is specific to his pairs' classifier and does not apply
here, independently verified below).

## Source and licence

- **BAREC-Shared-Task-2025-sent**, CC BY-SA 4.0. Raw files hashed: `c25577f23019a597` (train+dev+test
  concatenated, `scripts/barec_provenance.py::_barec_file_hash`). Re-derive with the fetch command in
  `data/README.md` and compare, to confirm no drift before reusing this export.
- **Pipeline code**: `scripts/barec_simplification_pipeline.py`, `validation.py`,
  `camel_readability.py`, `barec_provenance.py`, `dataset_split.py`. Built against upstream commit
  `56bb03d` (2026-09-25); this session's pipeline changes are not yet committed — see the PR that
  ships alongside this data card for the actual diff.
- **Generator**: DeepSeek V4.1 Flash (`deepseek/deepseek-flash`), `NUM_CANDIDATES=5` per source,
  temperature 0.7, `max_tokens=4096`. **Judge**: same model, temperature 0, `max_tokens=8192`,
  MIPROv2-compiled equivalence validator (`scripts/compiled/equivalence_validator.json`).
  **Readability**: CAMeL-Lab/readability-arabertv02-word-CE, fp32 ONNX, `TAU=0.33`. Both token
  budgets were raised mid-project (2048/4096 -> 4096/8192) after a drift check found truncation
  failures at the lower budgets; verified via a matched controlled test that the higher budgets did
  not inflate real completion-token usage for already-succeeding calls (see thresholds below).
- **Data is not in this repo.** `.gitignore` blocks `*.parquet`/`pred_*.jsonl`/`*_predictions.csv`
  repo-wide (licensed source text can't be redistributed via git). The actual pair data ships on
  Kaggle/HF private, referenced by this card's counts and hashes; only code + this card go in the PR.

## Acceptance thresholds and their calibration history

- `EQUIVALENCE_THRESHOLD = 0.70` — swept on a 25-pair held-out annotated set (84% accuracy at
  0.70-0.75 vs. 64% at a naive 0.8 guess); picked the lower/safer edge of that plateau. Small n,
  treated as directional.
- `TAU = 0.33` (readability gate, `d_logit >= TAU`) and `TIER_A_EQ_THRESHOLD = 0.85` (tier A vs. B
  split within passers) — see `scripts/barec_simplification_pipeline.py` inline comments for the
  full derivation.
- `ease_score` reranking formula (`0.1134*camel_logit - 0.6186*mean_aoa + 1.8605`): fit on 1,678 real
  SAMER full-sentence human-simplification pairs (not the minimal-pair SAMER variant, a
  mischaracterization caught and corrected mid-project — both sets of numbers are in
  `references/03_project_architecture/pipeline_architecture.tex` Section 4).

## Counts

Provisional export, 13,075 rows after BAREC-test-split exclusion (see below), before the split:

| pair_type | count |
|---|---|
| generated | 12,768 (tier A 7,492 / tier B 5,276, `readability_lead<=0` quarantine already excluded: 718 rows) |
| identity | 602 (~5%, selected by lowest mean AoA within the easy band, domain- and length-matched to the generated set — not by BAREC level, per the round-6 identity-pair consultation) |
| scripture | 100 |

After the train/dev/test split (`scripts/dataset_split.py`, stratified by level bucket x Domain x
pair_type, hash-bucket assignment, salt `bayan-split-v1`):

| split | count | notes |
|---|---|---|
| train | 10,377 | grows with every future batch resume |
| dev | 1,197 | frozen; new sources do not enter this split |
| test | 1,501 | frozen; drawn only from BAREC-train-sourced rows (BAREC-test is the project's own locked eval set, `data/test_manifest.json` — never touched) |

**Provenance deviation, stated plainly**: the default assumption going into this (inherit BAREC's
own train/dev boundary — our dev ⊆ BAREC-dev) turned out not to be viable. BAREC-dev contributed
only 111 accepted pairs to this export — far too few for a usable dev set on its own. So dev and
test are **both** hash-holdouts from the combined BAREC-train + BAREC-dev accepted pool, not dev
purely inherited from BAREC-dev. BAREC-test is **never** used to build any part of this export —
it remains the project's own locked eval set (`data/test_manifest.json`, hash-pinned) untouched by
generation, holdout selection, or anything else here. This is a deliberate decision, not an
oversight, and it changes what "held out" means for this dataset going forward.

**Reproducibility**: assignment is deterministic — `bucket = sha256(f"{SALT}:{source_id}")[:8] as
int, mod 10_000`, `SALT = "bayan-split-v1"` (`scripts/dataset_split.py`). Same salt + same rule
reproduces the identical split from the BAREC files alone (hash `c25577f23019a597`) plus the
provisional export; the resulting ID→split→stratum mapping is also committed verbatim at
`data/dataset_split.csv` (13,075 rows) so it never needs re-deriving by hand. Per-stratum target
sizes are proportional to each stratum's share of the eligible pool, scaled to the fixed global
targets (dev=1,200, test=1,500); realized counts (1,197 / 1,501) are within rounding of target by
construction. Bump `SALT` (never edit it in place) if the split is ever deliberately reset.

Split balance verified: standardized mean difference train-vs-dev/test on
equivalence_score/readability_lead/ease_score all < 0.03 (bar: < 0.1); a gradient-boosted classifier
trained to predict split membership from all numeric + categorical features scored AUC 0.509
(train/dev) and 0.513 (train/test) under 5-fold CV — indistinguishable from chance (bar: < 0.55).

## BAREC test-split exclusion

`load_and_clean_barec()` previously concatenated train+dev+test with no filter — a real,
confirmed gap against issue #8's explicit instruction. Fixed two ways: (1) the loader now labels
every row with `barec_split` (not a silent filter — an earlier design was rejected for exactly that
reason); (2) `scripts/barec_provenance.py` provides the actual exclusion authority
(`filter_barec()`), which also catches the case ID-matching alone misses: BAREC repeats 311
sentences between its own train and test splits (confirmed, pinned in
`scripts/test_barec_provenance.py`), so a train-sourced row's *text* can still leak into test under
a different ID. 395 rows removed from the 13,470-row provisional set on this basis (120 direct
test-split-ID matches + 275 additional text-level train/test crossings).

## Human-label quality profile (measured on a 100-source real-production audit, not this specific
## export — see caveat)

- **Real natural leak rate**: 1.0% strict (`meaning` == "changed"), 10.0% loose (changed + minor).
- **Not-genuinely-simpler rate: 20%** (`simpler` == same or harder) — the dominant measured defect,
  larger than the faithfulness leak by 2-20x depending on reading.
- **Fluency blind spot**: rule-based (mechanical) truncations caught 100% of the time (0/15 missed)
  by a human annotator; MiMo-generated (fluent) truncations missed 33.3% of the time (5/15) — fluent
  content-dropping evades detection far more than mechanical content-dropping, for a human, not just
  an LLM judge. This means the human labels themselves likely *underestimate* leak specifically for
  fluent generation, in the same direction DeepSeek's own output would be missed.
- **Caveat**: these rates are measured on a 100-source sample from the same pipeline/thresholds as
  this export, not a relabel of this export's specific 13,075 rows. Treat as the best available
  estimate of this export's defect rate, not an exact count. Test-split scores from a model trained
  on this data measure agreement with this pipeline's own notion of simplification, not independent
  simplification quality — the external instrument remains human rating on a sample.

## Known open items (why this is v0, not final)

- Morning relabel (4 strata, ~300-500 labels) not yet incorporated.
- `readability_lead` quarantine (718 rows) removed but not reviewed for recoverability.
- Multi-candidate acceptance (taking more than the single winner per source) evaluated and not yet
  adopted — same-pool tier-A candidates average 0.74 pairwise text similarity, mostly near-duplicate
  rather than independent signal; a diversity-filtered version is proposed but not implemented.
- CAMeL fp32 batch-independence verified (max probability diff 0.0, alone vs. batched with
  wildly different-length neighbors) — every `batch_size>1` computation in this pipeline
  (the readability-lead backfill, the split's stratification features) is unaffected by the
  int8-quantization batch-dependence bug that issue #12 describes for a different classifier.
- `check_leakage.py` run against the train split (20,754 sentences: `original_text` + `simplified_text`
  columns both checked) vs. the locked BAREC test set (`data/test_locked/barec_test.csv`, hash
  verified against `data/test_manifest.json`), with `--reachable train.csv --reachable dev.csv`:
  **no leakage found** — 0 matches of 5+ words. 21 short matches ignored as corpus noise (the
  tool's own `--min-words` convention), 16 of those also legitimately present in the reachable
  train+dev text (BAREC's own internal repetition, not leakage).
