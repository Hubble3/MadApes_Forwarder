"""DexScreener API client for MadApes Forwarder.

Includes retry with exponential backoff and circuit breaker to handle
transient failures and avoid hammering the API during outages.
"""
import asyncio
import logging
import time

import aiohttp

from madapes.constants import DS_CHAINS
from madapes.http_client import get_session

logger = logging.getLogger(__name__)

# Retry config
_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds — delays: 1s, 2s, 4s
_TIMEOUT = aiohttp.ClientTimeout(total=10)

# Circuit breaker state
_cb_failures = 0
_cb_open_until = 0.0
_CB_THRESHOLD = 5       # consecutive failures to trip
_CB_COOLDOWN = 60.0     # seconds before half-open retry


def _circuit_open() -> bool:
    """Check if circuit breaker is open (too many recent failures)."""
    return _cb_failures >= _CB_THRESHOLD and time.monotonic() < _cb_open_until


def _record_success():
    global _cb_failures
    _cb_failures = 0


def _record_failure():
    global _cb_failures, _cb_open_until
    _cb_failures += 1
    if _cb_failures >= _CB_THRESHOLD:
        _cb_open_until = time.monotonic() + _CB_COOLDOWN
        logger.warning(f"DexScreener circuit breaker OPEN — {_CB_COOLDOWN}s cooldown after {_cb_failures} failures")


def _parse_token_pairs(data, chain):
    """Parse DexScreener pairs response into our standard format."""
    if not data.get("pairs"):
        return None
    pairs = sorted(
        data["pairs"],
        key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
        reverse=True,
    )
    pair = pairs[0]
    base_token = pair.get("baseToken", {})
    volume = pair.get("volume", {})
    price_change = pair.get("priceChange", {}) or {}
    api_chain = DS_CHAINS.get(chain, "ethereum") if chain else ""

    return {
        "price": pair.get("priceUsd"),
        "price_change_24h": price_change.get("h24"),
        "price_change_5m": price_change.get("m5"),
        "price_change_1h": price_change.get("h1"),
        "volume_24h": volume.get("h24"),
        "volume_1h": volume.get("h1"),
        "volume_5m": volume.get("m5"),
        "liquidity": pair.get("liquidity", {}).get("usd"),
        "fdv": pair.get("fdv"),
        "pair_address": pair.get("pairAddress"),
        "pair_url": pair.get("url"),
        "pair_created_at": pair.get("pairCreatedAt"),
        "chain": pair.get("chainId", api_chain),
        "token_name": base_token.get("name", ""),
        "token_symbol": base_token.get("symbol", ""),
        "exchange": pair.get("dexId", ""),
    }


async def _fetch_with_retry(url: str, label: str = "") -> dict | None:
    """GET a DexScreener URL with retry + backoff + circuit breaker."""
    if _circuit_open():
        logger.debug(f"DexScreener circuit open, skipping {label}")
        return None

    session = await get_session()
    last_error = None

    for attempt in range(_MAX_RETRIES):
        try:
            async with session.get(url, timeout=_TIMEOUT) as response:
                if response.status == 200:
                    _record_success()
                    return await response.json()
                if response.status == 429:
                    # Rate limited — back off longer
                    delay = _BASE_DELAY * (2 ** attempt) * 2
                    logger.debug(f"DexScreener 429 rate limited, waiting {delay:.1f}s")
                    await asyncio.sleep(delay)
                    continue
                if response.status >= 500:
                    # Server error — retry
                    last_error = f"HTTP {response.status}"
                else:
                    # 4xx (not 429) — don't retry
                    logger.debug(f"DexScreener returned {response.status} for {label}")
                    return None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_error = str(e)

        if attempt < _MAX_RETRIES - 1:
            delay = _BASE_DELAY * (2 ** attempt)
            logger.debug(f"DexScreener retry {attempt + 1}/{_MAX_RETRIES} for {label} in {delay:.1f}s")
            await asyncio.sleep(delay)

    _record_failure()
    logger.debug(f"DexScreener failed after {_MAX_RETRIES} retries for {label}: {last_error}")
    return None


async def fetch_token_data(chain, address):
    """Fetch token data from DexScreener API for a contract address."""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"
    data = await _fetch_with_retry(url, label=address[:8])
    if data is None:
        return None
    result = _parse_token_pairs(data, chain)
    if result is None:
        logger.debug(f"No pairs found for {address[:8]}...")
    return result


async def fetch_ticker_data(ticker):
    """Fetch token data from DexScreener API for a ticker symbol."""
    url = f"https://api.dexscreener.com/latest/dex/search?q={ticker}"
    data = await _fetch_with_retry(url, label=ticker)
    if data is None:
        return None
    if not data.get("pairs"):
        return None
    pairs = sorted(
        data["pairs"],
        key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
        reverse=True,
    )
    pair = pairs[0]
    volume = pair.get("volume", {}) or {}
    return {
        "price": pair.get("priceUsd"),
        "price_change_24h": (pair.get("priceChange") or {}).get("h24"),
        "volume_24h": volume.get("h24"),
        "volume_1h": volume.get("h1"),
        "volume_5m": volume.get("m5"),
        "liquidity": pair.get("liquidity", {}).get("usd"),
        "fdv": pair.get("fdv"),
    }
