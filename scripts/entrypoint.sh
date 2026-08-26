#!/bin/sh
# Single entrypoint: train on real data (if needed), then replay + worker + API

set -e

# Auto-train on real data if model bundle is missing
if [ ! -f "/app/models/model.joblib" ]; then
    echo "🔧 Model not found. Training on real dataset (normal rows, first 80% of time)..."
    python -m scripts.train_model
    echo "✅ Training complete."
fi

# Start real-data replay stream in background
echo "🚀 Starting real-data replay (held-out 20% of dataset)..."
python -m src.replay &
REPLAY_PID=$!

# Start detection worker in background
echo "🚀 Starting detection worker..."
python -m src.worker &
WORKER_PID=$!

# Start FastAPI server in foreground (keeps container alive)
echo "🚀 Starting API server on port 8000..."
exec uvicorn src.api:app --host 0.0.0.0 --port 8000
