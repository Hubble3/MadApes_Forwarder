"""Enrichment service - DexScreener data with Redis caching and rate limiting."""
import logging
from typing import Optional

from dexscreener import fetch_token_data, fetch_ticker_data
from madapes.redis_client import cache_get, cache_set, rate_limit_check

logger = logging.getLogger(__name__)

# Cache TTL for DexScreener responses
DEXSCREENER_CACHE_TTL = 60  # seconds
# Rate limit: 30 calls per 60 seconds to DexScreener
DEXSCREENER_RATE_LIMIT = 30
DEXSCREENER_RATE_WINDOW = 60  # seconds


def _cache_key(chain: str, address: str) -> str:
    return f"dex:token:{chain}:{address}"


def _ticker_cache_key(ticker: str) -> str:
    return f"dex:ticker:{ticker}"


async def enrich_token(chain: str, address: str) -> Optional[dict]:
    """Fetch token data with caching and rate limiting.

    Returns DexScreener data dict or None.
    """
    key = _cache_key(chain, address)

    # Check cache first
    cached = await cache_get(key)
    if cached is not None:
        logger.debug(f"Cache hit for {address[:8]}...")
        return cached

    # Rate limit check
    allowed = await rate_limit_check("ratelimit:dexscreener", DEXSCREENER_RATE_LIMIT, DEXSCREENER_RATE_WINDOW)
    if not allowed:
        logger.warning(f"Rate limited - skipping DexScreener fetch for {address[:8]}...")
        return None

    # Fetch from API
    data = await fetch_token_data(chain, address)
    if data:
        await cache_set(key, data, ttl_seconds=DEXSCREENER_CACHE_TTL)
        logger.debug(f"Cached DexScreener data for {address[:8]}...")
    return data


async def enrich_ticker(ticker: str) -> Optional[dict]:
    """Fetch ticker data with caching and rate limiting."""
    key = _ticker_cache_key(ticker)

    cached = await cache_get(key)
    if cached is not None:
        return cached

    allowed = await rate_limit_check("ratelimit:dexscreener", DEXSCREENER_RATE_LIMIT, DEXSCREENER_RATE_WINDOW)
    if not allowed:
        logger.warning(f"Rate limited - skipping DexScreener fetch for ${ticker}")
        return None

    data = await fetch_ticker_data(ticker)
    if data:
        await cache_set(key, data, ttl_seconds=DEXSCREENER_CACHE_TTL)
    return data


async def enrich_signal_data(chain: str, address: str, token_type: str = "contract", ticker: str = "") -> Optional[dict]:
    """High-level enrichment: route to correct fetcher based on token type."""
    if token_type == "contract":
        return await enrich_token(chain, address)
    elif ticker:
        return await enrich_ticker(ticker)
    return None
