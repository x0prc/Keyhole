"""Train RandomForest fraud classifier with honest time-based splits.

Split (time-ordered, no leakage):
- first 64% of time → fit (all rows, labels used — supervised)
- next  16% of time → validation (threshold selection only)
- last  20% of time → held-out test (streamed live; never seen here)

Threshold: highest recall on validation subject to precision >= 0.8.
"""
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from src import config
from src.replay import iter_dataset, TIME_SPAN, build_feature_vector

CUT_FIT = TIME_SPAN * 0.64
CUT_TEST = TIME_SPAN * 0.8
PRECISION_TARGET = 0.8


def load_splits():
    fit, val = [], []
    for elapsed, amount, v, is_fraud in iter_dataset():
        x = build_feature_vector(amount, v)
        if elapsed < CUT_FIT:
            fit.append((x, is_fraud))
        elif elapsed < CUT_TEST:
            val.append((x, is_fraud))
    return fit, val


def pick_threshold(probs: np.ndarray, y: np.ndarray) -> float:
    """Highest-recall threshold meeting PRECISION_TARGET on validation."""
    best_t, best_r = 0.5, -1.0
    for t in np.arange(0.30, 0.95, 0.01):
        pred = probs >= t
        tp = int((pred & (y == 1)).sum())
        fp = int((pred & (y == 0)).sum())
        if tp + fp == 0:
            continue
        p, r = tp / (tp + fp), tp / max(y.sum(), 1)
        if p >= PRECISION_TARGET and r > best_r:
            best_t, best_r = t, r
    return best_t


def main() -> None:
    fit, val = load_splits()
    X_fit, y_fit = np.vstack([x for x, _ in fit]), np.array([y for _, y in fit])
    X_val, y_val = np.vstack([x for x, _ in val]), np.array([y for _, y in val])
    print(f"fit: {len(y_fit):,} txns ({y_fit.sum()} fraud) | val: {len(y_val):,} txns ({y_val.sum()} fraud)")

    scaler = StandardScaler().fit(X_fit)
    model = RandomForestClassifier(
        n_estimators=100, class_weight="balanced", random_state=42, n_jobs=-1
    )
    model.fit(scaler.transform(X_fit), y_fit)

    threshold = pick_threshold(model.predict_proba(scaler.transform(X_val))[:, 1], y_val)

    joblib.dump(
        {"model": model, "scaler": scaler, "threshold": threshold},
        config.MODEL_PATH,
    )
    print(f"Saved {config.MODEL_PATH} — threshold={threshold:.2f} (P>={PRECISION_TARGET} on val)")


if __name__ == "__main__":
    main()
