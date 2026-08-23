"""Train Isolation Forest on the real dataset's train split (normal txns only).

Train split: first 80% of dataset time span, fraud rows excluded —
standard practice for anomaly detection. The last 20% is the held-out
live stream used for honest precision/recall evaluation.
"""
import numpy as np

from src.detector import FraudDetector
from src.replay import train_rows


def build_feature_vector(amount: float, v: list[float]) -> np.ndarray:
    """29-dim: V1..V28 + log1p(amount) — log-scale tames heavy-tailed amounts."""
    return np.array(v + [np.log1p(amount)], dtype=np.float64)


def main() -> None:
    X = np.vstack([build_feature_vector(a, v) for a, v in train_rows()])
    print(f"Loaded {len(X)} normal training rows (first 80% of time span)")

    detector = FraudDetector()
    # Real fraud rate is 0.17% — keep contamination tight for honest precision
    detector.fit(X, contamination=0.002)
    print("Model + scaler saved.")


if __name__ == "__main__":
    main()
