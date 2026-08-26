"""Central configuration — env overrides, sensible defaults."""
import os

# Kafka
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Dataset (real Kaggle creditcardfraud CSV)
DATASET_PATH = os.getenv("DATASET_PATH", "data/creditcard.csv")

# Detection — single joblib bundle: {"model", "scaler", "threshold"}
MODEL_PATH = os.getenv("MODEL_PATH", "models/model.joblib")
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "0.5"))  # fallback if no bundle
