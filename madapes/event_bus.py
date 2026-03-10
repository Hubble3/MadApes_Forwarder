"""Event bus - publishes and subscribes to events via Redis pub/sub."""
import logging
from typing import Callable, Awaitable

from madapes.events import (
    CHANNEL_SIGNAL_DETECTED,
    CHANNEL_SIGNAL_ENRICHED,
    CHANNEL_SIGNAL_FORWARDED,
    CHANNEL_PERFORMANCE_CHECKED,
    CHANNEL_RUNNER_DETECTED,
)
from madapes.redis_client import publish, subscribe

logger = logging.getLogger(__name__)

# Map event types to channels
_EVENT_CHANNELS = {
    "SignalDetected": CHANNEL_SIGNAL_DETECTED,
    "SignalEnriched": CHANNEL_SIGNAL_ENRICHED,
    "SignalForwarded": CHANNEL_SIGNAL_FORWARDED,
    "PerformanceChecked": CHANNEL_PERFORMANCE_CHECKED,
    "RunnerDetected": CHANNEL_RUNNER_DETECTED,
}

# API base URL for cross-process broadcasting
_API_URL = "http://127.0.0.1:8000"


async def _broadcast_to_api(event_type: str, event_data: dict):
    """Push event to the API server's WebSocket clients via HTTP."""
    try:
        from madapes.http_client import get_session
        session = await get_session()
        async with session.post(
            f"{_API_URL}/api/internal/broadcast",
            json={"event_type": event_type, "data": event_data},
            timeout=2,
        ) as resp:
            if resp.status == 200:
                logger.debug(f"Broadcast to API: {event_type}")
    except Exception:
        # API might not be running — that's fine
        pass


async def emit(event):
    """Publish an event to the appropriate Redis channel.
    The event must have a to_dict() method.
    """
    event_data = event.to_dict()
    event_type = event_data.get("event_type", type(event).__name__)
    channel = _EVENT_CHANNELS.get(event_type)
    if not channel:
        logger.warning(f"No channel mapped for event type: {event_type}")
        return
    await publish(channel, event_data)
    logger.debug(f"Event emitted: {event_type} on {channel}")

    # Broadcast to API server's WebSocket clients (cross-process)
    await _broadcast_to_api(event_type, event_data)


async def on(event_type: str, callback: Callable[[str, dict], Awaitable[None]]):
    """Subscribe to events of a given type.
    callback receives (channel: str, data: dict).
    """
    channel = _EVENT_CHANNELS.get(event_type)
    if not channel:
        logger.warning(f"No channel mapped for event type: {event_type}")
        return
    await subscribe(channel, callback)
    logger.debug(f"Subscribed to {event_type} on {channel}")
