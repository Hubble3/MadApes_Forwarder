"""Redis client for MadApes Forwarder - pub/sub, caching, rate limiting."""
import asyncio
import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_redis = None
_pubsub_task: Optional[asyncio.Task] = None
_subscribers: dict = {}  # channel -> [callback, ...]


async def get_redis():
    """Get or create the shared Redis connection."""
    global _redis
    if _redis is not None:
        try:
            await _redis.ping()
            return _redis
        except Exception:
            _redis = None

    from config import REDIS_URL
    if not REDIS_URL:
        logger.warning("REDIS_URL not set - Redis features disabled")
        return None

    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(
            REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=5,
            retry_on_timeout=True,
        )
        await _redis.ping()
        logger.info(f"Redis connected: {REDIS_URL}")
        return _redis
    except ImportError:
        logger.warning("redis package not installed - Redis features disabled")
        return None
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        _redis = None
        return None


async def close_redis():
    """Close the Redis connection."""
    global _redis, _pubsub_task
    if _pubsub_task and not _pubsub_task.done():
        _pubsub_task.cancel()
        _pubsub_task = None
    if _redis is not None:
        await _redis.aclose()
        _redis = None


# --- Pub/Sub ---

async def publish(channel: str, data: dict):
    """Publish a JSON message to a Redis channel."""
    r = await get_redis()
    if r is None:
        # Fallback: call local subscribers directly
        await _dispatch_local(channel, data)
        return
    try:
        await r.publish(channel, json.dumps(data))
    except Exception as e:
        logger.error(f"Redis publish failed on {channel}: {e}")
        await _dispatch_local(channel, data)


async def subscribe(channel: str, callback):
    """Register an async callback for a Redis pub/sub channel.
    The callback receives (channel: str, data: dict).
    """
    if channel not in _subscribers:
        _subscribers[channel] = []
    _subscribers[channel].append(callback)
    await _ensure_pubsub_listener()


async def _dispatch_local(channel: str, data: dict):
    """Dispatch to local subscribers (fallback when Redis unavailable)."""
    for cb in _subscribers.get(channel, []):
        try:
            await cb(channel, data)
        except Exception as e:
            logger.error(f"Subscriber error on {channel}: {e}")


async def _ensure_pubsub_listener():
    """Start the background pub/sub listener if not already running."""
    global _pubsub_task
    if _pubsub_task and not _pubsub_task.done():
        return

    r = await get_redis()
    if r is None:
        return

    _pubsub_task = asyncio.create_task(_pubsub_loop(r))


async def _pubsub_loop(r):
    """Background loop that listens to all subscribed channels."""
    try:
        pubsub = r.pubsub()
        channels = list(_subscribers.keys())
        if not channels:
            return
        await pubsub.subscribe(*channels)
        logger.info(f"Redis pub/sub listening on: {channels}")

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            channel = message["channel"]
            try:
                data = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                continue
            await _dispatch_local(channel, data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Redis pub/sub loop error: {e}")


# --- Caching ---

async def cache_get(key: str) -> Optional[dict]:
    """Get a cached JSON value."""
    r = await get_redis()
    if r is None:
        return None
    try:
        val = await r.get(key)
        if val:
            return json.loads(val)
    except Exception as e:
        logger.debug(f"Cache get error for {key}: {e}")
    return None


async def cache_set(key: str, data: dict, ttl_seconds: int = 60):
    """Set a cached JSON value with TTL."""
    r = await get_redis()
    if r is None:
        return
    try:
        await r.set(key, json.dumps(data), ex=ttl_seconds)
    except Exception as e:
        logger.debug(f"Cache set error for {key}: {e}")


# --- Rate Limiting ---

async def rate_limit_check(key: str, max_calls: int, window_seconds: int) -> bool:
    """Sliding window rate limiter. Returns True if allowed, False if rate-limited."""
    r = await get_redis()
    if r is None:
        return True  # No Redis = no rate limiting

    try:
        import time
        now = time.time()
        pipe = r.pipeline()
        # Remove old entries
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        # Add current call
        pipe.zadd(key, {str(now): now})
        # Count calls in window
        pipe.zcard(key)
        # Set expiry on the key
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        count = results[2]
        return count <= max_calls
    except Exception as e:
        logger.debug(f"Rate limit check error for {key}: {e}")
        return True
