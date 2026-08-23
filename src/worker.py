"""Kafka consumer: score real transactions, emit alerts + live txn feed."""
import asyncio
import json
import signal

from aiokafka import AIOKafkaConsumer
from redis.asyncio import Redis

from src import config
from src.detector import FraudDetector
from src.metrics_tracker import record_prediction
from src.replay import RealTransaction
from src.alerts import create_real_alert


class DetectionWorker:
    """Async worker: consume → score → metrics → alert + broadcast."""

    def __init__(self) -> None:
        self.consumer: AIOKafkaConsumer | None = None
        self.redis: Redis | None = None
        self.detector = FraudDetector()
        self._shutdown = asyncio.Event()

    async def start(self) -> None:
        self.redis = Redis.from_url(config.REDIS_URL, decode_responses=True)
        self.consumer = AIOKafkaConsumer(
            config.KAFKA_TOPIC,
            bootstrap_servers=config.KAFKA_BOOTSTRAP,
            value_deserializer=lambda m: json.loads(m.decode("utf-8")),
            auto_offset_reset="latest",
            group_id="fraud-detector",
        )
        await self.consumer.start()
        print("Worker started. Waiting for transactions...")

        try:
            async for msg in self.consumer:
                if self._shutdown.is_set():
                    break
                await self._process(msg.value)
        finally:
            await self.consumer.stop()
            await self.redis.aclose()

    async def _process(self, data: dict) -> None:
        try:
            txn = RealTransaction(**data)

            # 29-dim real feature vector: V1..V28 + log-amount
            import numpy as np
            x = np.array(txn.v_features + [np.log1p(txn.amount)], dtype=np.float64)
            is_fraud, score = self.detector.predict_vector(x)

            # Ground-truth metrics (labels never influence the model)
            await record_prediction(self.redis, txn.is_fraud, is_fraud)

            # Broadcast every txn for the live dashboard feed
            feed = {
                "txn_id": txn.txn_id,
                "timestamp": txn.timestamp,
                "amount": txn.amount,
                "currency": txn.currency,
                "is_fraud_actual": txn.is_fraud,
                "predicted_fraud": is_fraud,
                "score": round(score, 4),
            }
            await self.redis.lpush("transactions:recent", json.dumps(feed))
            await self.redis.ltrim("transactions:recent", 0, 99)
            await self.redis.publish("transactions", json.dumps(feed))

            if is_fraud:
                alert = await create_real_alert(self.redis, txn, score)
                if alert:
                    print(
                        f"ALERT {alert['alert_id']} amount=€{txn.amount:.2f} "
                        f"score={score:.3f} true_label={txn.is_fraud}"
                    )
        except Exception as e:
            print(f"Error processing txn: {e}")

    def stop(self) -> None:
        self._shutdown.set()


async def main() -> None:
    worker = DetectionWorker()

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, worker.stop)

    await worker.start()


if __name__ == "__main__":
    asyncio.run(main())
