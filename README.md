# 🔑 Keyhole — Fraud Spike Detector

Real-time fraud spike detection system for **Razorpay AI Buildathon 2025** (Track 02: AI Risk Manager).

## What It Does

Detects fraudulent card transactions in a live stream:
- Trained on the **Kaggle Credit Card Fraud dataset** (284,807 real transactions, 492 frauds)
- Isolation Forest over 29 real PCA features (V1–V28) + log-scaled amount
- **Honest held-out evaluation**: first 80% of the dataset's 48h time span = training (normal only), last 20% = live stream with ground-truth labels
- Threshold calibrated on train data to a target false-positive rate — precision/recall reported live on the dashboard

## Architecture

4-container setup: Kafka (streaming), Zookeeper (coordination), Redis (state), App (detection + API + dashboard).

## Quick Start

```bash
# 1. Clone and enter
cd Keyhole

# 2. Get the dataset (requires Kaggle API key in ~/.kaggle/credentials.json)
cd data && kaggle datasets download -d mlg-ulb/creditcardfraud && unzip -o creditcardfraud.zip && cd ..

# 3. Train the model — pick ONE:
#    a) Kaggle notebook (recommended, free compute): open notebooks/keyhole_training.ipynb
#       on kaggle.com, run all cells, download keyhole_model.joblib → models/isolation_forest.joblib
#    b) Local: pip install -e . && python -m scripts.train_model

# 4. Start everything
docker compose up --build

# 5. Open dashboard
open http://localhost:8000/dashboard/
```

## Tech Stack

- Python 3.11 + asyncio
- Kafka (Confluent 7.5) + aiokafka
- Redis 7 + redis-py (async)
- scikit-learn Isolation Forest
- FastAPI + WebSocket
- Vanilla HTML/JS dashboard

## Evaluation

Held-out 20% (73,766 transactions, 98 frauds) — see `notebooks/keyhole_training.ipynb` for the operating-point sweep. Default operating point targets 0.5% FPR.

## License

MIT — Built for Razorpay AI Buildathon.
