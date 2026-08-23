"""Central configuration — env overrides, sensible defaults."""
import os

# Kafka
KAFKA_BOOTSTRAP = os.getenv("KAFKA_BOOTSTRAP", "localhost:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")
KAFKA_ALERTS_TOPIC = os.getenv("KAFKA_ALERTS_TOPIC", "alerts")

# Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Generator
FRAUD_RATE = float(os.getenv("FRAUD_RATE", "0.05"))
GENERATOR_TPS = int(os.getenv("GENERATOR_TPS", "50"))
NUM_MERCHANTS = int(os.getenv("NUM_MERCHANTS", "20"))

# Dataset (real Kaggle creditcardfraud CSV)
DATASET_PATH = os.getenv("DATASET_PATH", "data/creditcard.csv")

# Detection
ANOMALY_THRESHOLD = float(os.getenv("ANOMALY_THRESHOLD", "-0.15"))
MODEL_PATH = os.getenv("MODEL_PATH", "models/isolation_forest.joblib")
SCALER_PATH = os.getenv("SCALER_PATH", "models/scaler.joblib")
ALERT_DEDUP_TTL = int(os.getenv("ALERT_DEDUP_TTL", "60"))

# Feature windows (seconds)
WINDOW_1M = 60
WINDOW_5M = 300
WINDOW_15M = 900

# API
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
