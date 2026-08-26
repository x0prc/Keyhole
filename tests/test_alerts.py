"""Tests for alerting."""
import json
import pytest
import pytest_asyncio
import fakeredis.aioredis

from src.alerts import create_real_alert, _severity


class FakeTxn:
    txn_id = "txn_test"
    timestamp = 1700000000.0
    amount = 149.62
    currency = "EUR"
    is_fraud = True


@pytest_asyncio.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.aclose()


def test_severity_bands():
    assert _severity(-0.9) == "high"
    assert _severity(-0.5) == "medium"
    assert _severity(-0.1) == "low"


@pytest.mark.asyncio
async def test_create_real_alert(redis_client):
    alert = await create_real_alert(redis_client, FakeTxn(), -0.9)
    assert alert["severity"] == "high"
    assert alert["is_true_fraud"] is True

    stored = json.loads(await redis_client.lindex("alerts:recent", 0))
    assert stored["alert_id"] == alert["alert_id"]
