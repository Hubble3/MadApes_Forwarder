"""FastAPI application for MadApes Forwarder dashboard."""
import sys
import os

# Add project root to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from db import init_database
from api.routes import signals, callers, portfolio, analytics, leaderboard, runners, webhooks, ml, settings, strategies, insights
from api.websocket import websocket_endpoint, broadcast, update_bot_heartbeat, get_bot_status


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    init_database()
    yield
    from madapes.http_client import close_session
    await close_session()


app = FastAPI(
    title="MadApes Signal Intelligence API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS for dashboard — configurable via CORS_ORIGINS env var
_cors_env = os.getenv("CORS_ORIGINS", "").strip()
_cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else [
    "http://localhost:3000", "http://127.0.0.1:3000",
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(signals.router, prefix="/api/signals", tags=["signals"])
app.include_router(callers.router, prefix="/api/callers", tags=["callers"])
app.include_router(portfolio.router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
app.include_router(runners.router, prefix="/api/runners", tags=["runners"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
app.include_router(ml.router, prefix="/api/ml", tags=["ml"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(strategies.router, prefix="/api/strategies", tags=["strategies"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/bot-status")
async def bot_status():
    """Get current bot online/offline status."""
    return get_bot_status()


@app.post("/api/internal/broadcast")
async def internal_broadcast(request: Request):
    """Internal endpoint for bot process to push events to WebSocket clients."""
    data = await request.json()
    event_type = data.get("event_type", "unknown")
    event_data = data.get("data", {})
    await broadcast(event_type, event_data)
    return {"ok": True}


@app.post("/api/internal/heartbeat")
async def internal_heartbeat(request: Request):
    """Internal endpoint for bot to report its status."""
    data = await request.json()
    update_bot_heartbeat(data)
    return {"ok": True}
