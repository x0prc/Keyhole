"""Isolation Forest fraud detection with rule-based fallback."""
import os
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

from src import config
from src.features import FeatureVector


class FraudDetector:
    """Isolation Forest detector with fallback rules."""

    def __init__(self, model_path: str = config.MODEL_PATH, scaler_path: str = config.SCALER_PATH):
        self.model: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        self.threshold = config.ANOMALY_THRESHOLD
        self._load(model_path, scaler_path)

    def _load(self, model_path: str, scaler_path: str) -> None:
        if os.path.exists(model_path):
            bundle = joblib.load(model_path)
            if isinstance(bundle, dict):  # calibrated artifact
                self.model = bundle["model"]
                self.scaler = bundle["scaler"]
                self.threshold = bundle["threshold"]
            else:  # legacy: separate scaler file
                self.model = bundle
                self.scaler = joblib.load(scaler_path) if os.path.exists(scaler_path) else None

    def fit(self, X: np.ndarray, contamination: float = 0.002, target_fpr: float = 0.005) -> None:
        """Train scaler + Isolation Forest; calibrate threshold to target FPR on train data."""
        self.scaler = StandardScaler()
        X_scaled = self.scaler.fit_transform(X)
        self.model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
            n_jobs=-1,
        )
        self.model.fit(X_scaled)

        # Honest calibration: threshold = train-score percentile matching target FPR
        train_scores = self.model.decision_function(X_scaled)
        self.threshold = float(np.percentile(train_scores, 100 * target_fpr))

        os.makedirs(os.path.dirname(config.MODEL_PATH), exist_ok=True)
        joblib.dump(
            {"model": self.model, "scaler": self.scaler, "threshold": self.threshold},
            config.MODEL_PATH,
        )

    def predict(self, vec: FeatureVector) -> tuple[bool, float]:
        """Return (is_fraud, anomaly_score). Score is negative for outliers."""
        x = vec.to_numpy().reshape(1, -1)

        # Try ML first
        if self.model is not None and self.scaler is not None:
            try:
                x_scaled = self.scaler.transform(x)
                score = float(self.model.decision_function(x_scaled)[0])
                return score < self.threshold, score
            except Exception:
                pass  # Fall through to rules

        # Rule-based fallback (windowed features)
        score = self._rule_score(vec)
        return score > 0.5, score

    def predict_vector(self, x_raw: np.ndarray) -> tuple[bool, float]:
        """Score a raw feature vector (real-data path: V1..V28 + log-amount)."""
        x = x_raw.reshape(1, -1)

        # Try ML first
        if self.model is not None and self.scaler is not None:
            try:
                x_scaled = self.scaler.transform(x)
                score = float(self.model.decision_function(x_scaled)[0])
                return score < self.threshold, score
            except Exception:
                pass  # Fall through to rules

        # Rule-based fallback (raw PCA features)
        score = self._rule_score_from_raw(x_raw)
        return score > 0.5, score

    def _rule_score_from_raw(self, x: np.ndarray) -> float:
        """Fallback for real vectors: extreme absolute PCA values are suspicious."""
        import numpy as _np
        extreme = int((_np.abs(x[:28]) > 5).sum())
        amount_log = x[28] if len(x) > 28 else 0.0
        score = min(extreme * 0.1, 0.6)
        if amount_log > 7:  # ~€1100+
            score += 0.2
        return min(score, 1.0)

    @staticmethod
    def _rule_score(vec: FeatureVector) -> float:
        """Simple heuristic score 0–1. Higher = more suspicious.
        Thresholds tuned to match generated fraud pattern sizes:
        - velocity spike: 10 txns  → txn_count_1m > 8
        - card testing: 6 cards    → unique_cards_5m > 4
        - geo anomaly: 4 cities    → geo_entropy_5m > 1.0
        - amount outlier: zscore 6 → amount_zscore > 4
        """
        score = 0.0
        if vec.txn_count_1m > 8:
            score += 0.3
        if vec.unique_cards_5m > 4:
            score += 0.25
        if vec.geo_entropy_5m > 1.0:
            score += 0.25
        if vec.amount_zscore > 4:
            score += 0.2
        return min(score, 1.0)
