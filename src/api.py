"""FastAPI: REST metrics + WebSocket alert stream."""
import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from redis.asyncio import Redis

from src import config
from src.metrics_tracker import get_counts, calculate_metrics


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = Redis.from_url(config.REDIS_URL, decode_responses=True)
    yield
    await app.state.redis.close()


app = FastAPI(title="Keyhole — Fraud Spike Detector", lifespan=lifespan)
app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics")
async def metrics():
    """Live precision, recall, F1, false positive rate — computed from ground truth."""
    redis = app.state.redis
    counts = await get_counts(redis)
    return calculate_metrics(counts)


@app.get("/alerts")
async def list_alerts(limit: int = 50):
    redis = app.state.redis
    raw = await redis.lrange("alerts:recent", 0, limit - 1)
    return [json.loads(r) for r in raw]


@app.get("/transactions/recent")
async def recent_transactions(limit: int = 100):
    """Last N processed transactions with predictions and ground truth."""
    redis = app.state.redis
    raw = await redis.lrange("transactions:recent", 0, limit - 1)
    return [json.loads(r) for r in raw]


@app.websocket("/ws/transactions")
async def websocket_transactions(ws: WebSocket):
    """Live transaction feed for the dashboard."""
    await ws.accept()
    redis = app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe("transactions")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("transactions")


@app.websocket("/ws/alerts")
async def websocket_alerts(ws: WebSocket):
    await ws.accept()
    redis = app.state.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe("alerts")

    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                await ws.send_text(message["data"])
    except WebSocketDisconnect:
        await pubsub.unsubscribe("alerts")


@app.get("/")
async def root():
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head><meta http-equiv="refresh" content="0; url=/dashboard/"></head>
    <body>Redirecting to dashboard...</body>
    </html>
    """)
