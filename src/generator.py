"""Synthetic transaction generator with fraud injection."""
import asyncio
import json
import random
import uuid
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, Field

from src import config

# Merchant profiles: baseline tx/day, avg amount, cities, cards
MERCHANT_PROFILES = [
    {
        "merchant_id": f"merch_{i:03d}",
        "avg_amount": random.uniform(200, 8000),
        "amount_std": random.uniform(50, 1500),
        "cities": random.sample(
            ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata"],
            k=random.randint(1, 3),
        ),
        "cards": [f"card_{i:03d}_{j:03d}" for j in range(random.randint(5, 50))],
        "devices": [f"dev_{i:03d}_{j:03d}" for j in range(random.randint(3, 20))],
        "base_tps": random.uniform(0.5, 5.0),
    }
    for i in range(config.NUM_MERCHANTS)
]


class Transaction(BaseModel):
    txn_id: str = Field(default_factory=lambda: f"txn_{uuid.uuid4().hex[:12]}")
    merchant_id: str
    timestamp: float = Field(default_factory=lambda: datetime.now(timezone.utc).timestamp())
    amount: float
    currency: str = "INR"
    card_id: str
    device_id: str
    ip_address: str
    city: str
    is_fraud: bool = False


def _pick_ip(city: str) -> str:
    """Return a plausible Indian IP for a city."""
    octets = {
        "Bangalore": (103, 21, random.randint(0, 255)),
        "Mumbai": (103, 216, random.randint(0, 255)),
        "Delhi": (103, 27, random.randint(0, 255)),
        "Hyderabad": (103, 231, random.randint(0, 255)),
        "Chennai": (103, 5, random.randint(0, 255)),
        "Pune": (103, 203, random.randint(0, 255)),
        "Kolkata": (103, 240, random.randint(0, 255)),
    }
    a, b, c = octets.get(city, (103, 21, 0))
    return f"{a}.{b}.{c}.{random.randint(1, 254)}"


def _generate_normal(profile: dict) -> Transaction:
    """Generate a single normal transaction for a merchant."""
    return Transaction(
        merchant_id=profile["merchant_id"],
        amount=round(random.gauss(profile["avg_amount"], profile["amount_std"]), 2),
        card_id=random.choice(profile["cards"]),
        device_id=random.choice(profile["devices"]),
        ip_address=_pick_ip(random.choice(profile["cities"])),
        city=random.choice(profile["cities"]),
        is_fraud=False,
    )


def _generate_fraud_spike(profile: dict, spike_size: int = 10) -> list[Transaction]:
    """Velocity spike: burst of txns from same merchant, same card."""
    card = random.choice(profile["cards"])
    device = random.choice(profile["devices"])
    city = random.choice(profile["cities"])
    ip = _pick_ip(city)
    now = datetime.now(timezone.utc).timestamp()
    return [
        Transaction(
            merchant_id=profile["merchant_id"],
            timestamp=now + i * 0.5,
            amount=round(random.gauss(profile["avg_amount"], profile["amount_std"] * 0.3), 2),
            card_id=card,
            device_id=device,
            ip_address=ip,
            city=city,
            is_fraud=True,
        )
        for i in range(spike_size)
    ]


def _generate_card_testing(profile: dict, num_cards: int = 6) -> list[Transaction]:
    """Card testing: many small-amount txns with different cards."""
    device = random.choice(profile["devices"])
    city = random.choice(profile["cities"])
    ip = _pick_ip(city)
    now = datetime.now(timezone.utc).timestamp()
    cards = random.sample(profile["cards"], k=min(num_cards, len(profile["cards"])))
    return [
        Transaction(
            merchant_id=profile["merchant_id"],
            timestamp=now + i * 2.0,
            amount=round(random.uniform(10, 100), 2),
            card_id=card,
            device_id=device,
            ip_address=ip,
            city=city,
            is_fraud=True,
        )
        for i, card in enumerate(cards)
    ]


def _generate_geo_anomaly(profile: dict, num_cities: int = 4) -> list[Transaction]:
    """Geo anomaly: txns from many cities in short window."""
    card = random.choice(profile["cards"])
    device = random.choice(profile["devices"])
    all_cities = ["Bangalore", "Mumbai", "Delhi", "Hyderabad", "Chennai", "Pune", "Kolkata"]
    cities = random.sample(all_cities, k=num_cities)
    now = datetime.now(timezone.utc).timestamp()
    return [
        Transaction(
            merchant_id=profile["merchant_id"],
            timestamp=now + i * 30.0,
            amount=round(random.gauss(profile["avg_amount"], profile["amount_std"]), 2),
            card_id=card,
            device_id=device,
            ip_address=_pick_ip(city),
            city=city,
            is_fraud=True,
        )
        for i, city in enumerate(cities)
    ]


def _generate_amount_outlier(profile: dict) -> list[Transaction]:
    """Amount outlier: txn >> merchant average."""
    city = random.choice(profile["cities"])
    return [
        Transaction(
            merchant_id=profile["merchant_id"],
            amount=round(profile["avg_amount"] + profile["amount_std"] * random.uniform(6, 10), 2),
            card_id=random.choice(profile["cards"]),
            device_id=random.choice(profile["devices"]),
            ip_address=_pick_ip(city),
            city=city,
            is_fraud=True,
        )
    ]


FRAUD_GENERATORS = [
    _generate_fraud_spike,
    _generate_card_testing,
    _generate_geo_anomaly,
    _generate_amount_outlier,
]


async def generate_transactions(
    producer: AIOKafkaProducer,
    duration_seconds: int = 300,
) -> None:
    """Generate transactions and push to Kafka for `duration_seconds`."""
    end = asyncio.get_event_loop().time() + duration_seconds
    while asyncio.get_event_loop().time() < end:
        profile = random.choice(MERCHANT_PROFILES)

        if random.random() < config.FRAUD_RATE:
            # Inject fraud pattern
            gen = random.choice(FRAUD_GENERATORS)
            batch = gen(profile)
        else:
            batch = [_generate_normal(profile)]

        for txn in batch:
            await producer.send(
                config.KAFKA_TOPIC,
                json.dumps(txn.model_dump()).encode("utf-8"),
            )

        # Throttle to target TPS
        await asyncio.sleep(1.0 / config.GENERATOR_TPS)


async def main() -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP,
        value_serializer=lambda v: v,
    )
    await producer.start()
    try:
        await generate_transactions(producer)
    finally:
        await producer.stop()


if __name__ == "__main__":
    asyncio.run(main())
