"""Tests for alerting system."""
import pytest
import pytest_asyncio
import fakeredis.aioredis

from src.alerts import should_alert, create_alert, Alert
from src.features import FeatureVector
from src.generator import Transaction


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


@pytest.mark.asyncio
async def test_deduplication(redis_client):
    assert await should_alert(redis_client, "merch_001") is True
    assert await should_alert(redis_client, "merch_001") is False


@pytest.mark.asyncio
async def test_create_alert(redis_client):
    txn = Transaction(
        merchant_id="merch_001",
        amount=1000,
        card_id="card_001",
        device_id="dev_001",
        ip_address="103.21.58.1",
        city="Bangalore",
        is_fraud=True,
    )
    vec = FeatureVector(txn_count_1m=25, unique_cards_5m=12)
    alert = await create_alert(redis_client, txn, vec, -0.75, True)
    assert alert is not None
    assert alert.merchant_id == "merch_001"
    assert alert.severity == "high"
    assert "txn_count_1m" in alert.triggered_features
