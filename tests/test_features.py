"""Tests for feature engineering."""
import pytest
import pytest_asyncio
import fakeredis.aioredis
from src.generator import Transaction
from src.features import update_merchant_state, compute_features, FeatureVector


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=False)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.close()


@pytest.mark.asyncio
async def test_update_and_compute(redis_client):
    txn = Transaction(
        merchant_id="merch_test",
        amount=500.0,
        card_id="card_001",
        device_id="dev_001",
        ip_address="103.21.58.1",
        city="Bangalore",
        is_fraud=False,
    )
    await update_merchant_state(redis_client, txn)
    vec = await compute_features(redis_client, txn)
    assert vec.txn_count_1m == 1.0
    assert vec.amount_mean_5m == 500.0
    assert vec.unique_cards_5m == 1.0
