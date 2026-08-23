FROM python:3.11-slim

WORKDIR /app

# Install build deps for scikit-learn
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy all source files first
COPY pyproject.toml ./
COPY src/ ./src/
COPY scripts/ ./scripts/
COPY dashboard/ ./dashboard/
COPY models/ ./models/

# Install dependencies directly (no editable mode needed in container)
RUN pip install --no-cache-dir \
    fastapi>=0.100 \
    uvicorn[standard]>=0.23 \
    aiokafka>=0.9 \
    redis>=5.0 \
    scikit-learn==1.6.1 \
    joblib>=1.3 \
    numpy>=1.24 \
    pydantic>=2.0

# Set PYTHONPATH so `python -m src.xxx` works
ENV PYTHONPATH=/app

# Make scripts executable
RUN chmod +x scripts/*.sh

EXPOSE 8000

# Single entrypoint: train (if needed) → generator + worker + API
CMD ["sh", "/app/scripts/entrypoint.sh"]
