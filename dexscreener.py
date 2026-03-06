"""DexScreener API client for MadApes Forwarder."""
import logging

import aiohttp

from madapes.constants import DS_CHAINS
from madapes.http_client import get_session

logger = logging.getLogger(__name__)


async def fetch_token_data(chain, address):
    """Fetch token data from DexScreener API for a contract address."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/tokens/{address}"

        session = await get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("pairs") and len(data["pairs"]) > 0:
                    pairs = sorted(
                        data["pairs"],
                        key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0),
                        reverse=True,
                    )
                    pair = pairs[0]
                    base_token = pair.get("baseToken", {})
                    volume = pair.get("volume", {})
                    price_change = pair.get("priceChange", {}) or {}
                    api_chain = DS_CHAINS.get(chain, "ethereum")

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
                else:
                    logger.debug(f"No pairs found for {address[:8]}...")
            else:
                logger.debug(f"DexScreener returned {response.status} for {address[:8]}...")
    except Exception as e:
        logger.debug(f"Error fetching DexScreener data for {address[:8]}...: {e}")
    return None


async def fetch_ticker_data(ticker):
    """Fetch token data from DexScreener API for a ticker symbol."""
    try:
        url = f"https://api.dexscreener.com/latest/dex/search?q={ticker}"

        session = await get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("pairs") and len(data["pairs"]) > 0:
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
    except Exception as e:
        logger.debug(f"Error fetching DexScreener ticker data: {e}")
    return None
