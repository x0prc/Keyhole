"""Real-time metrics tracker: TP, FP, FN, TN counts in Redis."""
from redis.asyncio import Redis


async def record_prediction(redis: Redis, is_fraud_actual: bool, is_fraud_predicted: bool) -> None:
    """Record one prediction outcome for metrics calculation."""
    if is_fraud_actual and is_fraud_predicted:
        await redis.incr("metrics:tp")
    elif is_fraud_actual and not is_fraud_predicted:
        await redis.incr("metrics:fn")
    elif not is_fraud_actual and is_fraud_predicted:
        await redis.incr("metrics:fp")
    else:
        await redis.incr("metrics:tn")


async def get_counts(redis: Redis) -> dict:
    """Return current TP, FP, FN, TN counts."""
    keys = ["metrics:tp", "metrics:fp", "metrics:fn", "metrics:tn"]
    values = await redis.mget(keys)
    return {
        "tp": int(values[0] or 0),
        "fp": int(values[1] or 0),
        "fn": int(values[2] or 0),
        "tn": int(values[3] or 0),
    }


def calculate_metrics(counts: dict) -> dict:
    """Calculate precision, recall, f1, false_positive_rate from counts."""
    tp = counts["tp"]
    fp = counts["fp"]
    fn = counts["fn"]
    tn = counts["tn"]

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0

    total_predictions = tp + fp + fn + tn
    total_alerts = tp + fp

    return {
        "total_predictions": total_predictions,
        "total_alerts": total_alerts,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "true_negatives": tn,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "false_positive_rate": round(fpr, 3),
    }
