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

    # Broadcast to WebSocket clients if API is running
    try:
        from api.websocket import broadcast
        await broadcast(event_type, event_data)
    except ImportError:
        pass
    except Exception:
        pass


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
