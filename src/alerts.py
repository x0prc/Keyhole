"""Alert creation, deduplication, storage, and Pub/Sub."""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field
from redis.asyncio import Redis

from src import config
from src.features import FeatureVector
from src.generator import Transaction


class Alert(BaseModel):
    alert_id: str = Field(default_factory=lambda: f"alert_{uuid.uuid4().hex[:12]}")
    merchant_id: str
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    severity: str  # "low", "medium", "high"
    anomaly_score: float
    triggered_features: list[str]
    txn_ids: list[str]
    is_true_fraud: Optional[bool] = None


def _severity(score: float) -> str:
    if score < -0.6:
        return "high"
    if score < -0.4:
        return "medium"
    return "low"


def _triggered_features(vec: FeatureVector) -> list[str]:
    features = []
    if vec.txn_count_1m > 8:
        features.append("txn_count_1m")
    if vec.unique_cards_5m > 4:
        features.append("unique_cards_5m")
    if vec.amount_zscore > 4:
        features.append("amount_zscore")
    if vec.geo_entropy_5m > 1.0:
        features.append("geo_entropy_5m")
    return features


async def should_alert(redis: Redis, merchant_id: str) -> bool:
    """Check dedup key. True if alert should fire."""
    key = f"dedup:{merchant_id}"
    exists = await redis.exists(key)
    if exists:
        return False
    await redis.setex(key, config.ALERT_DEDUP_TTL, "1")
    return True


async def store_alert(redis: Redis, alert: Alert) -> None:
    """Store alert in Redis list and hash."""
    await redis.lpush("alerts:recent", alert.model_dump_json())
    await redis.ltrim("alerts:recent", 0, 999)  # Keep last 1000
    await redis.hset(f"alert:{alert.alert_id}", mapping={
        "merchant_id": alert.merchant_id,
        "timestamp": str(alert.timestamp),
        "severity": alert.severity,
        "anomaly_score": str(alert.anomaly_score),
        "triggered_features": ",".join(alert.triggered_features),
        "txn_ids": ",".join(alert.txn_ids),
        "is_true_fraud": str(alert.is_true_fraud) if alert.is_true_fraud is not None else "",
    })


async def publish_alert(redis: Redis, alert: Alert) -> None:
    """Publish alert to Pub/Sub channel for WebSocket broadcast."""
    await redis.publish("alerts", alert.model_dump_json())


async def create_real_alert(redis: Redis, txn, score: float) -> Optional[dict]:
    """Alert for a real-data transaction. No merchant dedup — every flagged
    txn matters in the held-out stream."""
    alert = {
        "alert_id": f"alert_{uuid.uuid4().hex[:12]}",
        "timestamp": txn.timestamp,
        "severity": _severity(score),
        "anomaly_score": score,
        "amount": txn.amount,
        "currency": txn.currency,
        "txn_ids": [txn.txn_id],
        "is_true_fraud": txn.is_fraud,
    }
    await redis.lpush("alerts:recent", json.dumps(alert))
    await redis.ltrim("alerts:recent", 0, 999)
    await redis.publish("alerts", json.dumps(alert))
    return alert


async def create_alert(
    redis: Redis,
    txn: Transaction,
    vec: FeatureVector,
    score: float,
    is_fraud: bool,
) -> Optional[Alert]:
    """Create, deduplicate, store, and publish an alert."""
    if not await should_alert(redis, txn.merchant_id):
        return None

    alert = Alert(
        merchant_id=txn.merchant_id,
        severity=_severity(score),
        anomaly_score=score,
        triggered_features=_triggered_features(vec),
        txn_ids=[txn.txn_id],
        is_true_fraud=txn.is_fraud,
    )
    await store_alert(redis, alert)
    await publish_alert(redis, alert)
    return alert
