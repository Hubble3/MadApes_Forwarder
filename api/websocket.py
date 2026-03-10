"""WebSocket support for real-time signal feed."""
import asyncio
import json
import logging
from typing import Set

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

# Connected clients
_clients: Set[WebSocket] = set()


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
