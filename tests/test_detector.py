"""Tests for fraud detector."""
import numpy as np
import pytest

from src.detector import FraudDetector
from src.features import FeatureVector


def test_rule_fallback():
    detector = FraudDetector(model_path="nonexistent", scaler_path="nonexistent")
    vec = FeatureVector(txn_count_1m=25, unique_cards_5m=12, amount_zscore=6.0)
    is_fraud, score = detector.predict(vec)
    assert is_fraud is True
    assert score > 0.5


def test_rule_normal():
    detector = FraudDetector(model_path="nonexistent", scaler_path="nonexistent")
    vec = FeatureVector(txn_count_1m=1, unique_cards_5m=1, amount_zscore=0.5)
    is_fraud, score = detector.predict(vec)
    assert is_fraud is False


def test_fit_and_predict():
    detector = FraudDetector()
    X = np.random.randn(200, 10)
    detector.fit(X, contamination=0.05)
    vec = FeatureVector(*X[0].tolist())
    is_fraud, score = detector.predict(vec)
    assert isinstance(is_fraud, bool)
    assert isinstance(score, float)
