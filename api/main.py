"""FastAPI application for MadApes Forwarder dashboard."""
import sys
import os

# Add project root to path so we can import project modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from db import init_database
from api.routes import signals, callers, portfolio, analytics, leaderboard, runners, webhooks, ml
from api.websocket import websocket_endpoint


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

# CORS for dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
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


@app.websocket("/ws")
async def ws(websocket: WebSocket):
    await websocket_endpoint(websocket)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
