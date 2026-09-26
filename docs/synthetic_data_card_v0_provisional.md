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
not yet incorporated a planned relabel of the accepted pairs (four strata: `lead<=0`, near-margin
`d_logit-TAU`, tier A/B boundary, spike-in retest). Numbers here are the honest current state, not
a final release.

Closes the DeepSeek-pipeline portion of issue #8 (a second, external pipeline's pairs were dropped
from that issue's scope, agreed directly with its owner — see issue #12, specific to that other
pipeline's classifier and confirmed not to apply here, see below).

**Review history**: this export was reviewed and returned with five confirmed issues (a split-
freezing bug, a cross-split text-duplication bug, reranking weights fit on a locked eval split, a
counts inconsistency and stale wording in this card, and missing scripts for reproducibility). All
five are fixed in this version; see "Review fixes" below for what changed and why.

## Source and licence

- **BAREC-Shared-Task-2025-sent**, CC BY-SA 4.0. Raw files hashed: `c25577f23019a597` (train+dev+test
  concatenated, `scripts/barec_provenance.py::_barec_file_hash`). Re-derive with the fetch command in
  `data/README.md` and compare, to confirm no drift before reusing this export.
- **Pipeline code**: `scripts/barec_simplification_pipeline.py`, `validation.py`,
  `camel_readability.py`, `lexical_scorer.py`, `barec_provenance.py`, `dataset_split.py`,
  `assemble_provisional_export.py`, `fit_ease_score_weights.py`, `rate_words_llm.py` — the full set
  needed to reproduce this export from a fresh clone.
- **Generator**: DeepSeek V4.1 Flash (`deepseek/deepseek-flash`), `NUM_CANDIDATES=5` per source,
  temperature 0.7, `max_tokens=4096`. **Judge**: same model, temperature 0, `max_tokens=8192`,
  MIPROv2-compiled equivalence validator (`scripts/compiled/equivalence_validator.json`).
  **Readability**: CAMeL-Lab/readability-arabertv02-word-CE, fp32 ONNX, `TAU=0.33`.
- **Data is not in this repo.** `.gitignore` blocks `*.parquet`/`pred_*.jsonl`/`*_predictions.csv`
  repo-wide (licensed source text can't be redistributed via git). The actual pair data ships on
  HF, public (BAREC's licence permits it) — see counts and hashes below; only code + this card go
  in the PR.

## Acceptance thresholds and their calibration history

- `EQUIVALENCE_THRESHOLD = 0.70` — swept on a 25-pair held-out annotated set (84% accuracy at
  0.70-0.75 vs. 64% at a naive 0.8 guess); picked the lower/safer edge of that plateau. Small n,
  treated as directional.
- `TAU = 0.33` (readability gate, `d_logit >= TAU`) and `TIER_A_EQ_THRESHOLD = 0.85` (tier A vs. B
  split within passers) — see `scripts/barec_simplification_pipeline.py` inline comments for the
  full derivation.
- `ease_score` reranking formula (`0.1121*camel_logit - 0.5777*mean_aoa + 1.7292`,
  `EASE_FORMULA_VERSION = "samer_train_2feat_v3"`): fit by `scripts/fit_ease_score_weights.py` on
  8,310 real SAMER full-sentence pairs from SAMER's **train** split
  (`data/processed/readability_compare_inputs/samer_train.parquet`). Held-out 5-fold CV recall at a
  10% reversed-pair false-accept rate: CAMeL alone 59.6%, combined 75.1%.
  **Superseded v2** (`samer_fullsentence_2feat_v2`) was fit on `samer_test.parquet` — SAMER's own
  **locked** eval split (`data/test_manifest.json`) — found in review; refitting on train data was
  verified against the original methodology first (recovered from the session record and confirmed
  by exactly reproducing its documented test-split numbers, 59.0%/70.4%/78.4%, to within rounding)
  before trusting the train-split result.

## Counts

Provisional export, 13,072 rows after BAREC-test-split exclusion (see below):

| pair_type | count |
|---|---|
| generated | 12,768 (tier A 7,494 / tier B 5,274, `readability_lead<=0` quarantine already excluded: 718 rows) |
| identity | ~600 (~5%, selected by lowest mean AoA within the easy band, domain- and length-matched to the generated set — not by BAREC level, which is only the floor/pool) |
| scripture | ~100 |

After the train/dev/test split (`scripts/dataset_split.py`, stratified by level bucket x Domain x
pair_type, frozen per-stratum hash-bucket thresholds, salt `bayan-split-v1`):

| split | count | notes |
|---|---|---|
| train | 10,327 | grows with every future batch resume |
| dev | 1,233 | frozen; new sources do not enter this split |
| test | 1,512 | frozen; drawn only from BAREC-train-sourced rows (BAREC-test is the project's own locked eval set, `data/test_manifest.json` — never touched) |

**Provenance deviation, stated plainly**: the default assumption going into this (inherit BAREC's
own train/dev boundary — our dev ⊆ BAREC-dev) turned out not to be viable. BAREC-dev contributed
only 111 accepted pairs to this export — far too few for a usable dev set on its own. So dev and
test are **both** hash-holdouts from the combined BAREC-train + BAREC-dev accepted pool, not dev
purely inherited from BAREC-dev. BAREC-test is **never** used to build any part of this export —
it remains the project's own locked eval set (`data/test_manifest.json`, hash-pinned) untouched by
generation, holdout selection, or anything else here. This is a deliberate decision, not an
oversight, and it changes what "held out" means for this dataset going forward.

**Reproducibility**: assignment is deterministic — every source is grouped by its own normalized
text first (so the same sentence under different BAREC IDs never splits across sides), then a
per-stratum hash-bucket **threshold** (not a target count) decides its split:
`bucket = sha256(f"{SALT}:{canonical_id}")[:8] as int, mod 10_000 < threshold[stratum]`,
`SALT = "bayan-split-v1"`. Thresholds are computed once and frozen in
`data/dataset_split_thresholds.json` (committed) — an earlier version recomputed a *target count*
from the current pool size on every run, which let a source's split silently drift as the pool
grew; fixed and verified (simulated pool growth of +2,000 rows: 0/13,072 existing IDs moved). The
resulting ID→split→stratum mapping is also committed verbatim at `data/dataset_split.csv` so it
never needs re-deriving by hand. Bump `SALT` (never edit it in place) for a deliberate reset.

Split balance verified: standardized mean difference train-vs-dev/test on
equivalence_score/readability_lead/ease_score all < 0.032 (bar: < 0.1); a gradient-boosted classifier
trained to predict split membership from all numeric + categorical features scored AUC 0.509
(train/dev) and 0.513 (train/test) under 5-fold CV — indistinguishable from chance (bar: < 0.55). No
source text appears in more than one split (asserted at build time).

## BAREC test-split exclusion

`load_and_clean_barec()` previously concatenated train+dev+test with no filter. Fixed three ways:
(1) the loader now labels every row with `barec_split` (not a silent filter — an earlier design was
rejected for exactly that reason); (2) `scripts/barec_provenance.py` provides the actual exclusion
authority (`filter_barec()`), which also catches the case ID-matching alone misses: BAREC repeats
315 sentences between its own train and test splits (confirmed, pinned in
`scripts/test_barec_provenance.py`; 311 by exact-text count alone, +4 once `normalize()` also strips
em/en-dash — a real gap found in review, since fixed) — a train-sourced row's *text* can still leak
into test under a different ID; (3) generation itself now skips BAREC-test-sourced sentences at the
sampling stage, not just at export, so they're never sent to the API in the first place. 398 rows
removed from the 13,470-row provisional set on this basis.

## Human-label quality profile (measured on a 100-source real-production audit, not this specific
## export — see caveat)

- **Real natural leak rate**: 1.0% strict (`meaning` == "changed"), 10.0% loose (changed + minor).
- **Not-genuinely-simpler rate: 20%** (`simpler` == same or harder) — the dominant measured defect,
  larger than the faithfulness leak by 2-20x depending on reading.
- **Fluency blind spot**: rule-based (mechanical) truncations caught 100% of the time (0/15 missed)
  by a human annotator; fluent (LLM-generated) truncations missed 33.3% of the time (5/15) — fluent
  content-dropping evades detection far more than mechanical content-dropping, for a human, not just
  an LLM judge. This means the human labels themselves likely *underestimate* leak specifically for
  fluent generation, in the same direction DeepSeek's own output would be missed.
- **Caveat**: these rates are measured on a 100-source sample from the same pipeline/thresholds as
  this export, not a relabel of this export's specific rows. Treat as the best available estimate
  of this export's defect rate, not an exact count. Scores from a model trained on this data and
  measured against its test split reflect agreement with this pipeline's own notion of
  simplification, not independent simplification quality — the external instrument remains human
  rating on a sample.

## Review fixes (this version)

A review of the previous version found five confirmed issues, independently verified before fixing,
all resolved here:

1. **Split wasn't frozen** — fixed (frozen hash-bucket thresholds, see Counts above).
2. **Grouped by ID, not text** — fixed (text-level grouping before assignment, see Counts above).
3. **`ease_score` fit on the locked SAMER test split** — fixed (refit on SAMER train, see
   Acceptance thresholds above).
4. **Counts inconsistency and session-narrative wording in this card** — fixed (this rewrite); the
   companion GitHub issue's "private" language also corrected to reflect the later, deliberate
   decision to publish openly.
5. **Not reproducible from a fresh clone** — fixed: `rate_words_llm.py` (the AoA table builder) and
   `assemble_provisional_export.py` (the actual export assembly, previously only a scratch script)
   are both now committed.

Also fixed: the `normalize()` dash gap noted above, and BAREC-test sentences no longer being sent to
DeepSeek during generation (previously dropped only at export, after real API spend on rows that
were always going to be discarded).

**Not yet addressed** (flagged in review, lower priority than the five above): ~780 generated pairs
come from very short (<=3 word) sources, mostly headings — real, but not judged a merge-blocker.

## Known open items (why this is v0, not final)

- Relabel of the accepted pairs (4 strata, ~300-500 labels) not yet incorporated.
- `readability_lead` quarantine (718 rows) removed but not reviewed for recoverability.
- Multi-candidate acceptance (taking more than the single winner per source) evaluated and not yet
  adopted — same-pool tier-A candidates average 0.74 pairwise text similarity, mostly near-duplicate
  rather than independent signal; a diversity-filtered version is proposed but not implemented.
- CAMeL fp32 batch-independence verified (max probability diff 0.0, alone vs. batched with
  wildly different-length neighbors) — every `batch_size>1` computation in this pipeline is
  unaffected by the int8-quantization batch-dependence bug that issue #12 describes for a different
  classifier.
- `check_leakage.py` run against the corrected train split (20,654 sentences: `original_text` +
  `simplified_text` columns both checked) vs. the locked BAREC test set
  (`data/test_locked/barec_test.csv`, hash verified against `data/test_manifest.json`), with
  `--reachable train.csv --reachable dev.csv`: **no leakage found** — 0 matches of 5+ words. 23
  short matches ignored as corpus noise (the tool's own `--min-words` convention), 19 of those also
  legitimately present in the reachable train+dev text (BAREC's own internal repetition).
