"""WebSocket support for real-time signal feed."""
import asyncio
import json
import logging
import time
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Connected clients
_clients: Set[WebSocket] = set()

# Bot heartbeat tracking
_bot_last_heartbeat: float = 0.0
_bot_status_info: dict = {}

BOT_HEARTBEAT_TIMEOUT = 30  # seconds


async def websocket_endpoint(websocket: WebSocket):
    """WebSocket handler for real-time signal updates."""
    await websocket.accept()
    _clients.add(websocket)
    logger.info(f"WebSocket client connected ({len(_clients)} total)")
    try:
        while True:
            # Keep connection alive, ignore client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        _clients.discard(websocket)
        logger.info(f"WebSocket client disconnected ({len(_clients)} total)")


async def broadcast(event_type: str, data: dict):
    """Broadcast an event to all connected WebSocket clients."""
    if not _clients:
        return
    message = json.dumps({"type": event_type, "data": data})
    disconnected = set()
    for client in list(_clients):
        try:
            await client.send_text(message)
        except Exception:
            disconnected.add(client)
    _clients -= disconnected


def update_bot_heartbeat(status_info: dict | None = None):
    """Record a bot heartbeat."""
    global _bot_last_heartbeat, _bot_status_info
    _bot_last_heartbeat = time.time()
    if status_info:
        _bot_status_info = status_info


def get_bot_status() -> dict:
    """Get current bot status."""
    now = time.time()
    is_online = (_bot_last_heartbeat > 0 and
                 (now - _bot_last_heartbeat) < BOT_HEARTBEAT_TIMEOUT)
    return {
        "online": is_online,
        "last_heartbeat": _bot_last_heartbeat,
        "seconds_ago": round(now - _bot_last_heartbeat, 1) if _bot_last_heartbeat > 0 else None,
        "info": _bot_status_info,
        "ws_clients": len(_clients),
    }
