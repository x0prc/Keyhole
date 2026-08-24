"""Replay real labeled transactions (Kaggle creditcardfraud) as a live Kafka stream.

Held-out evaluation design:
- First 80% of dataset time span  -> training (normal txns only)
- Last  20% of dataset time span  -> live stream (labels recorded, never shown to model)
"""
import asyncio
import csv
import json
import random
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, Field

from src import config

CSV_PATH = config.DATASET_PATH
TIME_SPAN = 172_792.0          # seconds covered by the dataset (48h)
TRAIN_FRACTION = 0.8
STREAM_DELAY = (4.0, 5.0)      # seconds between streamed txns (live demo pacing)
MAX_STREAM = 10_000            # cap the demo stream at 10K transactions


class RealTransaction(BaseModel):
    """A row from the real dataset, wrapped as a streaming event."""
    txn_id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}")
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    amount: float
    currency: str = "EUR"
    v_features: list[float]    # V1..V28 — real PCA features from the dataset
    is_fraud: bool             # ground-truth label (metrics only — model never sees it)


def iter_dataset(csv_path: str = CSV_PATH):
    """Yield (elapsed_seconds, amount, v_features, is_fraud) from the CSV."""
    with open(csv_path, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            elapsed = float(row[0])
            v = [float(x) for x in row[1:29]]
            amount = float(row[29])
            is_fraud = row[30] == "1"
            yield elapsed, amount, v, is_fraud


def train_rows(csv_path: str = CSV_PATH):
    """Normal rows from the first 80% of the time span — used to fit the model."""
    cutoff = TIME_SPAN * TRAIN_FRACTION
    for elapsed, amount, v, is_fraud in iter_dataset(csv_path):
        if elapsed >= cutoff:
            break
        if not is_fraud:
            yield amount, v


def stream_rows(csv_path: str = CSV_PATH):
    """All rows (incl. fraud) from the last 20% — the live held-out stream."""
    cutoff = TIME_SPAN * TRAIN_FRACTION
    for elapsed, amount, v, is_fraud in iter_dataset(csv_path):
        if elapsed < cutoff:
            continue
        yield elapsed - cutoff, amount, v, is_fraud


async def replay_stream(producer: AIOKafkaProducer) -> None:
    """Stream held-out rows to Kafka — one txn every 4–5s, capped at 10K."""
    sent = 0
    for _, amount, v, is_fraud in stream_rows():
        if sent >= MAX_STREAM:
            break
        txn = RealTransaction(amount=amount, v_features=v, is_fraud=is_fraud)
        await producer.send(
            config.KAFKA_TOPIC,
            json.dumps(txn.model_dump()).encode("utf-8"),
        )
        sent += 1
        if sent % 100 == 0:
            print(f"[replay] {sent}/{MAX_STREAM} transactions streamed...")
        await asyncio.sleep(random.uniform(*STREAM_DELAY))

    print(f"[replay] done — {sent} held-out transactions streamed")


async def main() -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        value_serializer=lambda v: v,
    )
    await producer.start()
    try:
        await replay_stream(producer)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
