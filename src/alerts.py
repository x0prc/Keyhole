"""Alert creation, storage, and Pub/Sub broadcast."""
import json
import uuid
from typing import Optional

from redis.asyncio import Redis


def _severity(score: float) -> str:
    """display_score is -probability for the supervised model: lower = worse."""
    if score < -0.6:
        return "high"
    if score < -0.4:
        return "medium"
    return "low"


async def create_real_alert(redis: Redis, txn, score: float) -> Optional[dict]:
    """Alert for a real-data transaction. No dedup — every flagged txn matters."""
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
