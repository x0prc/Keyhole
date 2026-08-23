"""Sliding-window feature engineering backed by Redis."""
import math
from dataclasses import dataclass
from typing import Optional

import numpy as np
from redis.asyncio import Redis

from src import config
from src.generator import Transaction


@dataclass
class FeatureVector:
    txn_count_1m: float = 0.0
    txn_count_5m: float = 0.0
    txn_count_15m: float = 0.0
    amount_mean_5m: float = 0.0
    amount_std_5m: float = 0.0
    unique_cards_5m: float = 0.0
    unique_ips_5m: float = 0.0
    unique_devices_5m: float = 0.0
    geo_entropy_5m: float = 0.0
    amount_zscore: float = 0.0

    def to_numpy(self) -> np.ndarray:
        return np.array(
            [
                self.txn_count_1m,
                self.txn_count_5m,
                self.txn_count_15m,
                self.amount_mean_5m,
                self.amount_std_5m,
                self.unique_cards_5m,
                self.unique_ips_5m,
                self.unique_devices_5m,
                self.geo_entropy_5m,
                self.amount_zscore,
            ],
            dtype=np.float64,
        )


def _entropy(counts: dict) -> float:
    """Shannon entropy over categorical counts."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    probs = [c / total for c in counts.values()]
    return -sum(p * math.log(p) for p in probs if p > 0)


async def update_merchant_state(redis: Redis, txn: Transaction) -> None:
    """Append transaction to merchant's Redis windows."""
    now = txn.timestamp
    merchant = txn.merchant_id

    # Main sorted set: all txns in 15m window
    key = f"merch:{merchant}:txns"
    member = f"{txn.txn_id}|{txn.amount}|{txn.card_id}|{txn.device_id}|{txn.ip_address}|{txn.city}"
    await redis.zadd(key, {member: now})
    await redis.expire(key, config.WINDOW_15M + 10)

    # Trim old entries
    await redis.zremrangebyscore(key, 0, now - config.WINDOW_15M)


async def compute_features(redis: Redis, txn: Transaction) -> FeatureVector:
    """Compute sliding-window feature vector for a merchant at current time."""
    now = txn.timestamp
    merchant = txn.merchant_id
    key = f"merch:{merchant}:txns"

    # Fetch entries in 15m window
    entries_15m = await redis.zrangebyscore(key, now - config.WINDOW_15M, now, withscores=True)
    entries_5m = [e for e in entries_15m if e[1] >= now - config.WINDOW_5M]
    entries_1m = [e for e in entries_5m if e[1] >= now - config.WINDOW_1M]

    # Parse 5m window for detailed stats
    amounts = []
    cards = set()
    ips = set()
    devices = set()
    cities = {}

    def _safe_decode(entry):
        return entry.decode() if isinstance(entry, bytes) else entry

    for entry, _ in entries_5m:
        parts = _safe_decode(entry).split("|")
        if len(parts) != 6:
            continue
        _, amount_str, card, device, ip, city = parts
        amounts.append(float(amount_str))
        cards.add(card)
        ips.add(ip)
        devices.add(device)
        cities[city] = cities.get(city, 0) + 1

    # Parse 15m window for baseline mean
    amounts_15m = []
    for entry, _ in entries_15m:
        parts = _safe_decode(entry).split("|")
        if len(parts) != 6:
            continue
        amounts_15m.append(float(parts[1]))

    vec = FeatureVector()
    vec.txn_count_1m = float(len(entries_1m))
    vec.txn_count_5m = float(len(entries_5m))
    vec.txn_count_15m = float(len(entries_15m))

    if amounts:
        vec.amount_mean_5m = float(np.mean(amounts))
        vec.amount_std_5m = float(np.std(amounts)) if len(amounts) > 1 else 0.0
        vec.unique_cards_5m = float(len(cards))
        vec.unique_ips_5m = float(len(ips))
        vec.unique_devices_5m = float(len(devices))
        vec.geo_entropy_5m = _entropy(cities)

        # Z-score vs 15m historical mean
        if amounts_15m and len(amounts_15m) > 1:
            hist_mean = np.mean(amounts_15m)
            hist_std = np.std(amounts_15m)
            if hist_std > 0:
                vec.amount_zscore = float((txn.amount - hist_mean) / hist_std)

    return vec
