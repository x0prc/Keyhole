"""Tests for synthetic transaction generator."""
import pytest
from src.generator import _generate_normal, _generate_fraud_spike, MERCHANT_PROFILES


def test_normal_transaction_shape():
    profile = MERCHANT_PROFILES[0]
    txn = _generate_normal(profile)
    assert txn.merchant_id == profile["merchant_id"]
    assert txn.currency == "INR"
    assert not txn.is_fraud
    assert txn.amount > 0


def test_fraud_spike_properties():
    profile = MERCHANT_PROFILES[0]
    batch = _generate_fraud_spike(profile, spike_size=10)
    assert len(batch) == 10
    assert all(t.is_fraud for t in batch)
    assert all(t.merchant_id == profile["merchant_id"] for t in batch)
    assert len({t.card_id for t in batch}) == 1  # Same card


def test_card_testing_properties():
    from src.generator import _generate_card_testing
    profile = MERCHANT_PROFILES[0]
    batch = _generate_card_testing(profile, num_cards=5)
    assert len(batch) == 5
    assert all(t.is_fraud for t in batch)
    assert all(t.amount <= 100 for t in batch)
    assert len({t.card_id for t in batch}) == 5
