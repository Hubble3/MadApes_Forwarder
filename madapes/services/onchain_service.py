"""On-chain analysis service - honeypot detection, safety scoring via GoPlus API."""
import logging
from typing import Optional

import aiohttp

from madapes.http_client import get_session
from madapes.redis_client import cache_get, cache_set

logger = logging.getLogger(__name__)

# GoPlus API (free, no key required for basic checks)
GOPLUS_BASE_URL = "https://api.gopluslabs.com/api/v1"

# Cache TTL for safety data (5 minutes - changes less frequently)
SAFETY_CACHE_TTL = 300

# Chain IDs for GoPlus API
GOPLUS_CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "base": "8453",
    "avalanche": "43114",
}


def _safety_cache_key(chain: str, address: str) -> str:
    return f"safety:{chain}:{address}"


async def check_token_safety(chain: str, address: str) -> Optional[dict]:
    """Check token safety via GoPlus Security API.

    Returns a safety analysis dict or None if unavailable.
    For Solana tokens, returns a basic result since GoPlus primarily supports EVM chains.
    """
    # Check cache first
    key = _safety_cache_key(chain, address)
    cached = await cache_get(key)
    if cached is not None:
        return cached

    chain_lower = chain.lower()

    # Solana: GoPlus has limited support, return basic result
    if chain_lower == "solana":
        result = _basic_safety_result(chain, address)
        await cache_set(key, result, ttl_seconds=SAFETY_CACHE_TTL)
        return result

    chain_id = GOPLUS_CHAIN_IDS.get(chain_lower)
    if not chain_id:
        return _basic_safety_result(chain, address)

    try:
        session = await get_session()
        url = f"{GOPLUS_BASE_URL}/token_security/{chain_id}?contract_addresses={address}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as response:
            if response.status != 200:
                logger.debug(f"GoPlus returned {response.status} for {address[:8]}...")
                return _basic_safety_result(chain, address)

            data = await response.json()
            if data.get("code") != 1:
                return _basic_safety_result(chain, address)

            result_data = data.get("result", {})
            # GoPlus returns data keyed by lowercase address
            token_data = result_data.get(address.lower(), {})
            if not token_data:
                return _basic_safety_result(chain, address)

            result = _parse_goplus_result(chain, address, token_data)
            await cache_set(key, result, ttl_seconds=SAFETY_CACHE_TTL)
            return result

    except Exception as e:
        logger.debug(f"GoPlus check failed for {address[:8]}...: {e}")
        return _basic_safety_result(chain, address)


def _parse_goplus_result(chain: str, address: str, data: dict) -> dict:
    """Parse GoPlus API response into our safety result format."""
    # Key risk flags
    is_honeypot = _flag(data.get("is_honeypot"))
    is_mintable = _flag(data.get("is_mintable"))
    is_proxy = _flag(data.get("is_proxy"))
    can_take_ownership = _flag(data.get("can_take_back_ownership"))
    has_external_call = _flag(data.get("external_call"))
    is_open_source = _flag(data.get("is_open_source"))
    buy_tax = _safe_pct(data.get("buy_tax"))
    sell_tax = _safe_pct(data.get("sell_tax"))
    owner_balance_pct = _safe_pct(data.get("owner_percent"))
    creator_balance_pct = _safe_pct(data.get("creator_percent"))
    holder_count = _safe_int(data.get("holder_count"))
    lp_holder_count = _safe_int(data.get("lp_holder_count"))
    is_anti_whale = _flag(data.get("is_anti_whale"))
    cannot_sell_all = _flag(data.get("cannot_sell_all"))
    is_blacklisted = _flag(data.get("is_blacklisted"))
    transfer_pausable = _flag(data.get("transfer_pausable"))

    # Compute safety score (0-100, higher = safer)
    score = 100.0

    # Critical risks (heavy penalties)
    if is_honeypot:
        score -= 80
    if cannot_sell_all:
        score -= 40
    if can_take_ownership:
        score -= 30

    # High risks
    if sell_tax is not None and sell_tax > 10:
        score -= min(30, sell_tax)
    if buy_tax is not None and buy_tax > 10:
        score -= min(20, buy_tax)
    if is_mintable:
        score -= 15
    if transfer_pausable:
        score -= 15
    if is_blacklisted:
        score -= 10

    # Medium risks
    if not is_open_source:
        score -= 10
    if is_proxy:
        score -= 10
    if has_external_call:
        score -= 5
    if owner_balance_pct is not None and owner_balance_pct > 20:
        score -= 10
    if creator_balance_pct is not None and creator_balance_pct > 30:
        score -= 10

    # Positive signals
    if holder_count is not None and holder_count > 100:
        score += 5
    if lp_holder_count is not None and lp_holder_count > 3:
        score += 5

    score = max(0, min(100, score))

    risks = []
    if is_honeypot:
        risks.append("HONEYPOT")
    if cannot_sell_all:
        risks.append("Cannot sell all")
    if can_take_ownership:
        risks.append("Ownership takeback")
    if sell_tax is not None and sell_tax > 5:
        risks.append(f"Sell tax {sell_tax:.0f}%")
    if buy_tax is not None and buy_tax > 5:
        risks.append(f"Buy tax {buy_tax:.0f}%")
    if is_mintable:
        risks.append("Mintable")
    if transfer_pausable:
        risks.append("Pausable")
    if not is_open_source:
        risks.append("Not open source")
    if is_proxy:
        risks.append("Proxy contract")

    return {
        "chain": chain,
        "address": address,
        "safety_score": round(score, 1),
        "is_honeypot": is_honeypot,
        "is_open_source": is_open_source,
        "is_mintable": is_mintable,
        "is_proxy": is_proxy,
        "buy_tax": buy_tax,
        "sell_tax": sell_tax,
        "holder_count": holder_count,
        "lp_holder_count": lp_holder_count,
        "owner_balance_pct": owner_balance_pct,
        "risks": risks,
        "source": "goplus",
    }


def _basic_safety_result(chain: str, address: str) -> dict:
    """Return a minimal safety result when API is unavailable."""
    return {
        "chain": chain,
        "address": address,
        "safety_score": None,
        "is_honeypot": None,
        "is_open_source": None,
        "is_mintable": None,
        "is_proxy": None,
        "buy_tax": None,
        "sell_tax": None,
        "holder_count": None,
        "lp_holder_count": None,
        "owner_balance_pct": None,
        "risks": [],
        "source": "none",
    }


def _flag(val) -> bool:
    """Parse GoPlus flag value ('1'/'0'/None) to bool."""
    if val is None:
        return False
    return str(val) == "1"


def _safe_pct(val) -> Optional[float]:
    """Parse a percentage string to float."""
    if val is None:
        return None
    try:
        return float(val) * 100 if float(val) <= 1 else float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> Optional[int]:
    """Parse an integer value."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def safety_badge(score: Optional[float]) -> str:
    """Return an HTML badge for the safety score."""
    if score is None:
        return ""
    if score >= 80:
        return "<b>[SAFE]</b>"
    elif score >= 50:
        return "<b>[CAUTION]</b>"
    elif score >= 20:
        return "<b>[RISKY]</b>"
    else:
        return "<b>[DANGER]</b>"


def safety_summary(result: dict) -> str:
    """Return a one-line summary for display in messages."""
    if not result or result.get("source") == "none":
        return ""
    score = result.get("safety_score")
    risks = result.get("risks", [])
    badge = safety_badge(score)
    if risks:
        risk_text = ", ".join(risks[:3])
        return f"{badge} {risk_text}"
    if score is not None and score >= 80:
        return f"{badge}"
    return badge
