#!/bin/sh
# Start both worker and API server

set -e

echo "Starting Keyhole Detection Worker..."
python -m src.worker &
WORKER_PID=$!

echo "Starting FastAPI Server..."
exec uvicorn src.api:app --host 0.0.0.0 --port 8000
