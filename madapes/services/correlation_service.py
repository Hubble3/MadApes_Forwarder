"""Multi-source correlation service - detects when multiple callers signal the same token."""
import logging
import time
from typing import Optional, Set

from madapes.redis_client import get_redis

logger = logging.getLogger(__name__)

# Window for multi-caller correlation
CORRELATION_WINDOW_SECONDS = 1800  # 30 minutes
CORRELATION_TTL_SECONDS = 3600     # Redis key TTL (1 hour)

# Local fallback when Redis is unavailable
_local_token_callers: dict = {}  # token_address -> {sender_id: timestamp, ...}


async def record_caller_for_token(token_address: str, sender_id: int) -> int:
    """Record that a caller signaled this token. Returns the number of unique callers
    within the correlation window.
    """
    r = await get_redis()
    if r is not None:
        return await _record_redis(r, token_address, sender_id)
    return _record_local(token_address, sender_id)


async def _record_redis(r, token_address: str, sender_id: int) -> int:
    """Use Redis SET with TTL for correlation tracking."""
    key = f"token:{token_address}:callers"
    try:
        now = time.time()
        pipe = r.pipeline()
        # Remove entries older than the window
        pipe.zremrangebyscore(key, 0, now - CORRELATION_WINDOW_SECONDS)
        # Add this caller (score = timestamp, member = sender_id)
        pipe.zadd(key, {str(sender_id): now})
        # Count unique callers
        pipe.zcard(key)
        # Set TTL
        pipe.expire(key, CORRELATION_TTL_SECONDS)
        results = await pipe.execute()
        count = results[2]
        return count
    except Exception as e:
        logger.error(f"Redis correlation error for {token_address}: {e}")
        return _record_local(token_address, sender_id)


def _record_local(token_address: str, sender_id: int) -> int:
    """Local fallback for correlation tracking."""
    now = time.time()
    if token_address not in _local_token_callers:
        _local_token_callers[token_address] = {}

    callers = _local_token_callers[token_address]
    # Prune old entries
    cutoff = now - CORRELATION_WINDOW_SECONDS
    expired = [sid for sid, ts in callers.items() if ts < cutoff]
    for sid in expired:
        del callers[sid]

    callers[sender_id] = now
    return len(callers)


async def get_callers_for_token(token_address: str) -> Set[int]:
    """Get the set of sender IDs that called this token within the window."""
    r = await get_redis()
    if r is not None:
        try:
            key = f"token:{token_address}:callers"
            now = time.time()
            await r.zremrangebyscore(key, 0, now - CORRELATION_WINDOW_SECONDS)
            members = await r.zrange(key, 0, -1)
            return {int(m) for m in members}
        except Exception as e:
            logger.error(f"Redis get_callers error: {e}")

    # Local fallback
    callers = _local_token_callers.get(token_address, {})
    now = time.time()
    cutoff = now - CORRELATION_WINDOW_SECONDS
    return {sid for sid, ts in callers.items() if ts >= cutoff}


def is_multi_caller(caller_count: int) -> bool:
    """Check if a token has been called by multiple sources."""
    return caller_count >= 2


def prune_local_cache():
    """Remove expired entries from local fallback. Called periodically."""
    now = time.time()
    cutoff = now - CORRELATION_TTL_SECONDS
    expired_tokens = []
    for token_address, callers in _local_token_callers.items():
        expired_sids = [sid for sid, ts in callers.items() if ts < cutoff]
        for sid in expired_sids:
            del callers[sid]
        if not callers:
            expired_tokens.append(token_address)
    for t in expired_tokens:
        del _local_token_callers[t]
