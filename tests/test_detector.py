"""Tests for fraud detector."""
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from src.detector import FraudDetector


def _write_bundle(tmp_path, threshold=0.5):
    """Train a tiny RF on separable data and save a bundle."""
    rng = np.random.RandomState(0)
    X = rng.randn(200, 29)
    y = (X[:, 0] > 1).astype(int)  # fraud = large V1
    scaler = StandardScaler().fit(X)
    model = RandomForestClassifier(n_estimators=10, random_state=0).fit(scaler.transform(X), y)
    import joblib
    p = tmp_path / "model.joblib"
    joblib.dump({"model": model, "scaler": scaler, "threshold": threshold}, p)
    return str(p)


def test_rule_fallback_when_no_model():
    det = FraudDetector(model_path="nonexistent.joblib")
    x = np.zeros(29); x[:6] = 8.0  # 6 extreme PCA values → score 0.6
    is_fraud, score = det.predict_vector(x)
    assert is_fraud is True and score > 0.5


def test_rule_fallback_normal():
    det = FraudDetector(model_path="nonexistent.joblib")
    is_fraud, score = det.predict_vector(np.zeros(29))
    assert is_fraud is False


def test_supervised_bundle_roundtrip(tmp_path):
    det = FraudDetector(model_path=_write_bundle(tmp_path))
    fraud_x = np.zeros(29); fraud_x[0] = 5.0  # large V1 = fraud in toy data
    normal_x = np.zeros(29)
    is_fraud, score = det.predict_vector(fraud_x)
    assert is_fraud is True and score < 0  # display score negated
    is_fraud_normal, _ = det.predict_vector(normal_x)
    assert is_fraud_normal is False
