"""Fraud detection: supervised RandomForest with rule-based fallback."""
import os
from typing import Optional

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from src import config


class FraudDetector:
    """Scores 29-dim feature vectors (V1..V28 + log-amount).

    Loads a joblib bundle: {"model", "scaler", "threshold"}.
    Supports supervised classifiers (predict_proba) and anomaly detectors
    (decision_function). display_score is negated so lower = more suspicious
    for downstream severity ranking.
    """

    def __init__(self, model_path: str = config.MODEL_PATH):
        self.model = None
        self.scaler: Optional[StandardScaler] = None
        self.threshold = config.ANOMALY_THRESHOLD
        self._load(model_path)

    def _load(self, model_path: str) -> None:
        if os.path.exists(model_path):
            bundle = joblib.load(model_path)
            self.model = bundle["model"]
            self.scaler = bundle["scaler"]
            self.threshold = bundle["threshold"]

    def predict_vector(self, x_raw: np.ndarray) -> tuple[bool, float]:
        """Return (is_fraud, display_score). display_score: lower = more suspicious."""
        if self.model is not None and self.scaler is not None:
            try:
                x_scaled = self.scaler.transform(x_raw.reshape(1, -1))
                if hasattr(self.model, "predict_proba"):
                    proba = float(self.model.predict_proba(x_scaled)[0, 1])
                    return proba >= self.threshold, -proba
                score = float(self.model.decision_function(x_scaled)[0])
                return score < self.threshold, score
            except Exception:
                pass  # Fall through to rules

        # Rule-based fallback: extreme absolute PCA values are suspicious
        score = self._rule_score_from_raw(x_raw)
        return score > 0.5, score

    @staticmethod
    def _rule_score_from_raw(x: np.ndarray) -> float:
        extreme = int((np.abs(x[:28]) > 5).sum())
        amount_log = x[28] if len(x) > 28 else 0.0
        score = min(extreme * 0.1, 0.6)
        if amount_log > 7:  # ~€1100+
            score += 0.2
        return min(score, 1.0)
