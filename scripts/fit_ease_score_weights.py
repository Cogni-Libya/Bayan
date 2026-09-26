"""Fit EASE_W_CAMEL_LOGIT / EASE_W_MEAN_AOA / EASE_INTERCEPT for barec_simplification_pipeline.py's
ease_score reranking formula, on SAMER's TRAIN split -- not test. The original fit used
samer_test.parquet, which is the project's own locked eval set (data/test_manifest.json); reusing
it to fit formula weights is the same kind of contamination as training on your own benchmark.

Methodology matches the original fit exactly (recovered from the session transcript and verified
by reproducing its reported numbers on samer_test to within rounding: CAMeL alone 59.00% vs. the
documented 59.0%, AoA alone 70.14% vs. 70.4%, combined 77.83% vs. 78.4%): 5-fold StratifiedKFold
cross_val_predict to get one set of held-out P(easier) probabilities for the whole pool, then for
each pair compute delta = P(easier|simplified) - P(easier|original) against its own reversal
(-delta) -- NOT a marginal-score quantile comparison across different pairs, which is a
substantially easier, non-comparable task (an earlier attempt at this refit used exactly that wrong
comparison and got recall figures 3x lower for no real reason other than measuring something else).

Usage: uv run python scripts/fit_ease_score_weights.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import numpy as np
import polars as pl
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict

from camel_readability import CamelReadability
from lexical_scorer import LexicalScorer

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SAMER_TRAIN = PROJECT_ROOT / "data" / "processed" / "readability_compare_inputs" / "samer_train.parquet"
FAR = 0.10


def _logit(p: np.ndarray) -> np.ndarray:
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def recall_at_far(oof_proba: np.ndarray, n: int, far: float = FAR) -> float:
    """oof_proba: held-out P(easier) for [n original texts, n simplified texts] concatenated."""
    p_o, p_m = oof_proba[:n], oof_proba[n:]
    delta = p_m - p_o
    rev = -delta
    thresh = np.sort(rev)[::-1][max(0, int(far * len(rev)) - 1)]
    return float(np.mean(delta >= thresh))


def main() -> None:
    df = pl.read_parquet(SAMER_TRAIN).filter(pl.col("L5") != pl.col("L3"))
    n = df.shape[0]
    print(f"{n} SAMER-train pairs with L5 != L3")

    orig, mod = df["L5"].to_list(), df["L3"].to_list()
    all_texts = orig + mod

    readability = CamelReadability()
    probs = readability.predict_probs(all_texts, batch_size=32)
    p_easy = readability.p_easy(probs)
    camel_logit = _logit(p_easy)

    lexical_scorer = LexicalScorer()
    mean_aoa = np.array([lexical_scorer.text(t)[0] for t in all_texts])

    # Direction check, empirical rather than assumed: confirm L3 is the easier level here too.
    print(f"mean P(easy) logit -- L5(orig): {camel_logit[:n].mean():.3f}   L3(mod): {camel_logit[n:].mean():.3f}")

    labels = np.array([0] * n + [1] * n)
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

    def cv_recall(X: np.ndarray) -> float:
        oof = cross_val_predict(LogisticRegression(max_iter=1000), X, labels, cv=cv, method="predict_proba")[:, 1]
        return recall_at_far(oof, n)

    X_camel = camel_logit.reshape(-1, 1)
    X_aoa = mean_aoa.reshape(-1, 1)
    X_combined = np.column_stack([camel_logit, mean_aoa])

    print("\n=== held-out (5-fold CV) recall @ 10% FAR, SAMER-train ===")
    print(f"CAMeL alone:  {cv_recall(X_camel):.4f}")
    print(f"AoA alone:    {cv_recall(X_aoa):.4f}")
    print(f"CAMeL + AoA:  {cv_recall(X_combined):.4f}")

    final_clf = LogisticRegression(max_iter=1000).fit(X_combined, labels)
    w_camel, w_aoa = final_clf.coef_[0]
    intercept = final_clf.intercept_[0]
    print(f"\nEASE_W_CAMEL_LOGIT = {w_camel:.4f}")
    print(f"EASE_W_MEAN_AOA = {w_aoa:.4f}")
    print(f"EASE_INTERCEPT = {intercept:.4f}")


if __name__ == "__main__":
    main()
