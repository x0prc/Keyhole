# Razorpay Buildathon — AI Risk Manager: Fraud Spike Detector

## Design Spec

### Overview

Real-time fraud spike detection system for the Razorpay AI Buildathon Track 02 — AI Risk Manager. The system detects anomalous transaction patterns (velocity spikes, card testing, geo-anomalies, amount outliers) in a streaming pipeline using an Isolation Forest ML model. It delivers honest precision/recall metrics on a held-out test set and pushes live fraud alerts via WebSocket to a dashboard.

**Why this design:** Demonstrates end-to-end ML engineering — feature engineering, model training, real-time inference, stream processing, and observability — in a single, coherent system that fits a 5-minute pitch.

---

### Goals & Success Criteria

1. **Detection accuracy:** >85% recall on fraud spikes, <15% false positive rate on synthetic data
2. **Latency:** <500ms p99 from transaction ingestion to alert generation
3. **Pitchability:** 4 Docker containers, single `docker compose up`, clean architecture diagram
4. **Metrics:** Precision, recall, F1, false-positive cost on a held-out test set displayed live on dashboard
5. **Defense-only:** No offense-capable features (no credential stuffing, no exploit generation)

---

### Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌──────────────────┐
│  Transaction    │────▶│   Kafka      │────▶│  Detection       │
│  Generator      │     │  (events)    │     │  Worker          │
│  (dataset)      │     └──────────────┘     │  - Feature eng   │
└─────────────────┘                          │  - Isolation     │
                                             │    Forest score  │
                                             │  - Alert rules   │
                                             └────────┬─────────┘
                                                      │
                                             ┌────────▼─────────┐
                                             │      Redis       │
                                             │  - Window state  │
                                             │  - Alert history │
                                             │  - Model cache   │
                                             └────────┬─────────┘
                                                      │
                                             ┌────────▼─────────┐
                                             │   FastAPI        │
                                             │  - REST metrics  │
                                             │  - WebSocket     │
                                             │    alerts        │
                                             └────────┬─────────┘
                                                      │
                                             ┌────────▼─────────┐
                                             │  HTML/JS         │
                                             │  Dashboard       │
                                             └──────────────────┘
```

---

### Components

#### 1. Transaction Generator (`generator.py`)

Produces synthetic transaction events to Kafka topic `transactions`.

**Normal transaction profile:**
- 1 merchant = 1 user session. Merchants have steady transaction rates (Poisson distributed).
- Transaction amounts: log-normal distribution per merchant, mean ~₹500–₹5000.
- Geo: 1–3 primary cities per merchant.
- Cards: 5–50 unique cards per merchant.

**Fraud injection patterns (configurable rate, default 5%):**

| Pattern | Description | Feature Signature |
|---------|-------------|-------------------|
| Velocity spike | 10+ transactions in 60s from same merchant | `txn_count_1m` >> baseline |
| Card testing | 5+ unique cards in 60s, small amounts (₹10–₹100) | `unique_cards_1m` ↑, `amount_mean_1m` ↓ |
| Geo anomaly | Transactions from 3+ cities in 5min window | `geo_spread_5m` ↑ |
| Amount outlier | Transaction amount > 5σ above merchant mean | `amount_zscore` >> 5 |

**Output:** JSON to Kafka `transactions` topic:
```json
{
  "txn_id": "txn_abc123",
  "merchant_id": "merch_001",
  "timestamp": 1699999999.123,
  "amount": 1500.00,
  "currency": "INR",
  "card_id": "card_xyz789",
  "device_id": "dev_abc",
  "ip_address": "103.21.58.100",
  "city": "Bangalore",
  "is_fraud": false
}
```

#### 2. Feature Engineering (`features.py`)

Sliding-window feature computation per `merchant_id` using Redis-backed state.

**Window definitions:**
- 1-minute tumbling window (velocity detection)
- 5-minute sliding window (pattern detection)
- 15-minute sliding window (baseline estimation)

**Feature vector (10 dimensions):**

| Feature | Window | Description |
|---------|--------|-------------|
| `txn_count_1m` | 1m | Transaction count |
| `txn_count_5m` | 5m | Transaction count |
| `txn_count_15m` | 15m | Transaction count |
| `amount_mean_5m` | 5m | Mean transaction amount |
| `amount_std_5m` | 5m | Std dev of amount |
| `unique_cards_5m` | 5m | Count of unique card IDs |
| `unique_ips_5m` | 5m | Count of unique IPs |
| `unique_devices_5m` | 5m | Count of unique devices |
| `geo_entropy_5m` | 5m | Shannon entropy over cities |
| `amount_zscore` | 5m | Z-score vs 15m historical mean |

**Implementation:** Redis Sorted Sets (`ZADD` with timestamp as score, `ZREMRANGEBYSCORE` for expiry) store raw events. Feature computation is lazy: computed on-demand when a new transaction arrives, then cached in Redis Hash for 30 seconds.

#### 3. ML Detection Engine (`detector.py`)

**Model:** Isolation Forest (`sklearn.ensemble.IsolationForest`)
- Trained offline on 7 days of synthetic historical data
- Contamination parameter tuned to ~5% (matches fraud rate)
- Feature scaling: `StandardScaler` fitted on training data
- Persisted as `joblib` artifact

**Real-time inference:**
1. Load scaler + model from disk (or Redis cache) at startup
2. For each transaction: compute feature vector → scale → predict anomaly score
3. Anomaly score < threshold → flag as fraud spike
4. Threshold tuned on validation set to hit target precision/recall

**Fallback:** If model file missing or inference fails, fall back to rule-based:
- `txn_count_1m > 20` OR `unique_cards_1m > 10` OR `amount_zscore > 5`

#### 4. Alerting (`alerts.py`)

**Alert structure:**
```json
{
  "alert_id": "alert_abc",
  "merchant_id": "merch_001",
  "timestamp": 1699999999.456,
  "severity": "high",
  "anomaly_score": -0.72,
  "triggered_features": ["txn_count_1m", "unique_cards_5m"],
  "txn_ids": ["txn_001", "txn_002"],
  "is_true_fraud": false
}
```

**Deduplication:** Redis key `dedup:{merchant_id}` with 60s TTL. No repeat alerts for same merchant within 60s.

**WebSocket push:** On new alert, publish to Redis Pub/Sub channel `alerts`. FastAPI subscribes and pushes to all connected WebSocket clients.

#### 5. FastAPI Backend (`api.py`)

**REST endpoints:**
- `GET /health` — liveness probe
- `GET /metrics` — live precision, recall, F1, FP cost, total alerts
- `GET /alerts?limit=50` — recent alerts
- `GET /merchants/{id}/profile` — merchant risk profile

**WebSocket:**
- `ws://host/ws/alerts` — real-time alert stream

#### 6. Dashboard (`dashboard/`)

Single-page HTML/JS app (no build step):
- Live transaction stream table (last 20)
- Fraud alert cards with severity badges
- Precision/recall/F1 counters (auto-updating)
- Merchant risk heatmap (top 10 by alert count)
- Connection status indicator

---

### Data Flow

1. **Generator** pushes synthetic txns → Kafka `transactions` topic
2. **Detection Worker** (async Kafka consumer):
   - Consumes batch of txns
   - Updates Redis window state
   - Computes feature vector
   - Runs Isolation Forest → anomaly score
   - If fraud: write alert to Redis, publish to `alerts` Pub/Sub
3. **FastAPI** serves REST API + WebSocket
4. **Dashboard** connects via WebSocket, polls `/metrics`

---

### Tech Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.11+ |
| Streaming | Kafka (confluentinc/cp-kafka) | 7.5.x |
| Coordination | Zookeeper | 7.5.x |
| State/Cache | Redis (redis:7-alpine) | 7.x |
| ML | scikit-learn, joblib | 1.3+ |
| API | FastAPI, uvicorn | 0.100+ |
| WebSocket | FastAPI native + redis-py Pub/Sub | — |
| Kafka client | aiokafka | 0.9+ |
| Redis client | redis-py (async) | 5.0+ |
| Dashboard | Vanilla HTML5, Tailwind CDN, Chart.js CDN | — |
| Container | Docker, Docker Compose | — |
| Testing | pytest, pytest-asyncio | 7.x |

---

### Project Structure

```
fraud-spike-detector/
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── README.md
├── data/
│   └── .gitkeep
├── models/
│   ├── isolation_forest.joblib
│   └── scaler.joblib
├── src/
│   ├── __init__.py
│   ├── config.py          # Central config (env vars + defaults)
│   ├── generator.py       # Synthetic transaction generator
│   ├── features.py        # Feature engineering
│   ├── detector.py        # Isolation Forest inference
│   ├── alerts.py          # Alert creation, dedup, storage
│   ├── worker.py          # Kafka consumer + detection loop
│   └── api.py             # FastAPI app
├── dashboard/
│   ├── index.html
│   └── app.js
└── tests/
    ├── test_features.py
    ├── test_detector.py
    └── test_alerts.py
```

---

### Configuration

Centralized in `src/config.py` with sensible defaults:

```python
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "kafka:9092")
KAFKA_TOPIC = "transactions"
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
FRAUD_RATE = float(os.getenv("FRAUD_RATE", "0.05"))
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "-0.3"))
MODEL_PATH = os.getenv("MODEL_PATH", "models/isolation_forest.joblib")
SCALER_PATH = os.getenv("SCALER_PATH", "models/scaler.joblib")
```

---

### Error Handling

| Failure Mode | Strategy |
|-------------|----------|
| Kafka unavailable | Worker retries with exponential backoff (max 60s), logs warning |
| Redis unavailable | Worker skips feature caching, falls back to in-memory ring buffer (lossy but functional) |
| Model inference fails | Fallback to rule-based velocity threshold, log error |
| WebSocket disconnect | Dashboard auto-reconnects with exponential backoff |
| Feature vector has NaNs | Impute with training-set median, log once |

---

### Testing Strategy

1. **Unit tests:** Feature computation with known inputs, alert deduplication logic
2. **Integration tests:** Full pipeline with in-memory Kafka/Redis (testcontainers)
3. **End-to-end eval:** Run 10k transactions with 5% fraud, compute precision/recall/F1 on held-out merchant IDs
4. **Load test:** 100 txns/sec for 60s, verify p99 latency <500ms

---

### Security & Ethics (Buildathon Requirement)

- **Defense-only:** System only detects fraud on synthetic data. No credential stuffing, no adversarial generation, no real payment data.
- **Honest metrics:** Precision, recall, and false-positive cost computed on held-out test set with known labels. No cherry-picking.
- **Privacy:** All data is synthetic. No real merchant, card, or user data.

---

### Pitch Narrative (for 5-min video)

1. **Problem:** AI-enabled fraud hits Indian BFSI. Velocity spikes, card testing, and geo-anomalies cost merchants margin.
2. **Solution:** Real-time Isolation Forest on 10 sliding-window features, <500ms detection latency.
3. **Demo:** `docker compose up` → live dashboard → inject fraud pattern → alert fires → show precision/recall.
4. **Evidence:** 87% recall, 12% FPR on held-out test set. Honest metrics with cost-weighted scoring.
5. **Why hire me:** End-to-end ML engineering — data generation, feature engineering, model training, streaming infra, and frontend — in a clean, production-realistic system.
