# 🔑 Keyhole

Real-time fraud detection for payment streams. Isolation Forest over Kafka, with honest held-out metrics and a live ops dashboard.

**Razorpay AI Buildathon — Track 02: AI Risk Manager** · defense-only

## Results

Held-out evaluation on the last 20% of the [Kaggle creditcardfraud](https://www.kaggle.com/datasets/mlg-ulb/creditcardfraud) time span (73,766 real transactions, 98 frauds) — the model never saw these during training:

| Precision | Recall | F1 | False-positive rate |
|-----------|--------|----|---------------------|
| 0.051     | 0.184  | 0.079 | 0.0046 (0.5% target) |

Operating point is calibrated on training scores, not hand-tuned. Full FPR↔recall sweep in `notebooks/keyhole_training.ipynb`.

## Architecture

```
transactions ──▶ Kafka ──▶ worker ──▶ Isolation Forest ──▶ Redis ──▶ FastAPI ──▶ dashboard
 (Kaggle CSV     (stream)   (scorer)   (29 real features)   (state)   (REST+WS)    (bento UI)
  replay, 500x)
```

4 containers, one command. First 80% of dataset time = train (normal txns only), last 20% = live held-out stream with ground-truth labels driving the live precision/recall.

## Quickstart

```bash
# 1. Get the dataset (needs Kaggle API key)
cd data && kaggle datasets download -d mlg-ulb/creditcardfraud && unzip creditcardfraud.zip && cd ..

# 2. Train (pick one)
python -m scripts.train_model          # local
# or run notebooks/keyhole_training.ipynb on Kaggle and drop the artifact into models/

# 3. Run everything
docker compose up --build

# 4. Dashboard
open http://localhost:8000/dashboard/
```

## Stack

Python 3.11 · aiokafka · Redis · scikit-learn · FastAPI + WebSocket · vanilla JS

## Docs

- `DESIGN.md` — architecture & threat model
- `notebooks/keyhole_training.ipynb` — reproducible training + evaluation
- `tests/` — 9 passing (`pytest`)

MIT License.
