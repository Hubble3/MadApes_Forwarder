"""Signal Strategy Engine - evaluates runner potential (0-100) for each signal.

Produces a runner_potential score separate from the existing confidence_score,
classifying signals into tiers: GOLD (75+), SILVER (50-74), BRONZE (25-49), SKIP (<25).
"""
import logging
import re
import time
from datetime import datetime
from typing import Optional

from db import get_connection
from utils import utcnow_naive

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level cache for chain momentum (5-minute TTL)
# ---------------------------------------------------------------------------
_chain_momentum_cache: dict = {"data": {}, "ts": 0.0}
_CHAIN_MOMENTUM_TTL = 300  # seconds

# ---------------------------------------------------------------------------
# Tier definitions
# ---------------------------------------------------------------------------
TIER_GOLD = "gold"
TIER_SILVER = "silver"
TIER_BRONZE = "bronze"
TIER_SKIP = "skip"

_TIER_META = {
    TIER_GOLD:   {"label": "GOLD",   "emoji": "\U0001f947"},   # 🥇
    TIER_SILVER: {"label": "SILVER", "emoji": "\U0001f948"},   # 🥈
    TIER_BRONZE: {"label": "BRONZE", "emoji": "\U0001f949"},   # 🥉
    TIER_SKIP:   {"label": "SKIP",   "emoji": "\u26d4"},       # ⛔
}

# Narrative keywords for message quality scoring
_NARRATIVE_KEYWORDS = {
    "team", "community", "utility", "narrative", "dev",
    "pushing", "building", "launched", "airdrop", "partnership",
}


# ===================================================================
# Public API
# ===================================================================

def compute_runner_potential(
    market_cap: float | None,
    liquidity: float | None,
    volume_24h: float | None,
    pair_created_at: str | None,
    chain: str | None,
    sender_id: int | None,
    message_text: str = "",
    has_plain_contract: bool = True,
) -> dict:
    """Evaluate a signal's runner potential.

    Returns:
        dict with keys:
            runner_potential (float 0-100),
            tier (str),
            components (dict of individual scores),
            tier_label (str),
            tier_emoji (str),
    """
    components = {
        "pair_freshness": _pair_freshness_score(pair_created_at),
        "mc_entry_zone": _mc_entry_zone_score(market_cap),
        "volume_momentum": _volume_momentum_score(volume_24h, market_cap),
        "caller_runner_history": _caller_runner_history_score(sender_id),
        "message_quality": _message_quality_score(message_text, has_plain_contract),
        "liquidity_health": _liquidity_health_score(liquidity, market_cap),
        "chain_momentum": _chain_momentum_score(chain),
    }

    total = sum(components.values())
    # Clamp to 0-100
    total = max(0.0, min(100.0, total))

    if total >= 75:
        tier = TIER_GOLD
    elif total >= 50:
        tier = TIER_SILVER
    elif total >= 25:
        tier = TIER_BRONZE
    else:
        tier = TIER_SKIP

    meta = _TIER_META[tier]

    return {
        "runner_potential": round(total, 1),
        "tier": tier,
        "components": components,
        "tier_label": meta["label"],
        "tier_emoji": meta["emoji"],
    }


def tier_label(tier: str) -> str:
    """Return display label for tier."""
    return _TIER_META.get(tier, _TIER_META[TIER_SKIP])["label"]


def tier_badge(tier: str, score: float) -> str:
    """Return HTML badge like '<b>[🥇 GOLD 82]</b>'."""
    meta = _TIER_META.get(tier, _TIER_META[TIER_SKIP])
    return f'<b>[{meta["emoji"]} {meta["label"]} {int(score)}]</b>'


# ===================================================================
# Scoring components
# ===================================================================

def _pair_freshness_score(pair_created_at: str | None) -> float:
    """Score 0-20 based on how recently the pair was created."""
    if not pair_created_at:
        return 0.0
    try:
        created = datetime.fromtimestamp(int(pair_created_at) / 1000)
        age_hours = (utcnow_naive() - created).total_seconds() / 3600
    except (ValueError, TypeError, OSError):
        return 0.0

    if age_hours < 2:
        return 20.0
    if age_hours < 6:
        return 17.0
    if age_hours < 12:
        return 14.0
    if age_hours < 24:
        return 10.0
    if age_hours < 72:   # 3 days
        return 6.0
    if age_hours < 168:  # 7 days
        return 3.0
    return 0.0


def _mc_entry_zone_score(market_cap: float | None) -> float:
    """Score 0-15 based on market cap entry zone."""
    if not market_cap or market_cap <= 0:
        return 0.0

    mc = market_cap
    if 100_000 <= mc <= 300_000:
        return 15.0   # golden zone
    if 50_000 <= mc < 100_000:
        return 12.0
    if 300_000 < mc <= 500_000:
        return 12.0
    if 500_000 < mc <= 1_000_000:
        return 8.0
    if 30_000 <= mc < 50_000:
        return 6.0    # ultra micro, risky
    if 1_000_000 < mc <= 5_000_000:
        return 4.0
    return 0.0


def _volume_momentum_score(volume_24h: float | None, market_cap: float | None) -> float:
    """Score 0-15 based on volume/market_cap ratio (buying pressure)."""
    if not volume_24h or not market_cap or market_cap <= 0:
        return 0.0

    ratio = volume_24h / market_cap

    if ratio > 2.0:
        return 15.0
    if ratio > 1.0:
        return 12.0
    if ratio > 0.5:
        return 9.0
    if ratio > 0.2:
        return 5.0
    if ratio > 0.1:
        return 2.0
    return 0.0


def _caller_runner_history_score(sender_id: int | None) -> float:
    """Score 0-15 based on the caller's historical runner rate."""
    if sender_id is None:
        return 0.0

    try:
        with get_connection() as conn:
            # Caller stats from callers table
            row = conn.execute(
                "SELECT total_signals, runner_count FROM callers WHERE sender_id = ?",
                (sender_id,),
            ).fetchone()

            total_checked = 0
            runner_count = 0
            if row:
                total_checked = row["total_signals"] or 0
                runner_count = row["runner_count"] or 0

            if total_checked < 5:
                return 0.0

            # Count big wins (runner_alerted with multiplier >= 5)
            big_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM signals "
                "WHERE sender_id = ? AND runner_alerted = 1 AND multiplier >= 5",
                (sender_id,),
            ).fetchone()
            big_wins = big_row["cnt"] if big_row else 0

    except Exception as exc:
        logger.warning("caller_runner_history_score error: %s", exc)
        return 0.0

    runner_rate = runner_count / total_checked
    big_win_rate = big_wins / total_checked

    if runner_rate >= 0.15:
        score = 15.0
    elif runner_rate >= 0.10:
        score = 12.0
    elif runner_rate >= 0.07:
        score = 9.0
    elif runner_rate >= 0.04:
        score = 6.0
    elif runner_rate >= 0.02:
        score = 3.0
    else:
        score = 0.0

    # Bonus for big wins
    if big_win_rate >= 0.05:
        score = min(15.0, score + 3.0)

    return score


def _message_quality_score(message_text: str, has_plain_contract: bool) -> float:
    """Score 0-15 based on message content quality signals."""
    if not message_text:
        return 0.0

    text_lower = message_text.lower()
    score = 0.0

    # Social links (+4)
    if "twitter.com" in text_lower or "x.com" in text_lower:
        score += 4.0

    # Narrative keywords (+1 each, max +5)
    keyword_hits = sum(1 for kw in _NARRATIVE_KEYWORDS if kw in text_lower)
    score += min(keyword_hits, 5)

    # DexScreener link/chart (+2)
    if "dexscreener.com" in text_lower:
        score += 2.0

    # Contract presented cleanly (+2)
    if has_plain_contract:
        score += 2.0

    # Minimal message penalty (-2)
    # Strip potential contract address (roughly 30-50 chars) to check actual content length
    stripped = re.sub(r"[A-Za-z0-9]{30,50}", "", message_text).strip()
    if len(stripped) < 20:
        score -= 2.0

    # Effort indicator: long message (+2)
    if len(message_text) > 100:
        score += 2.0

    # Clamp to 0-15
    return max(0.0, min(15.0, score))


def _liquidity_health_score(liquidity: float | None, market_cap: float | None) -> float:
    """Score 0-10 based on liquidity/market_cap ratio."""
    if not liquidity or not market_cap or market_cap <= 0:
        return 0.0

    ratio = liquidity / market_cap

    if 0.05 <= ratio <= 0.30:
        return 10.0   # healthy
    if 0.02 <= ratio < 0.05:
        return 6.0
    if 0.30 < ratio <= 0.50:
        return 5.0    # a bit high but okay
    # < 0.02 or > 0.50
    return 2.0


def _chain_momentum_score(chain: str | None) -> float:
    """Score 0-10 based on recent runner activity on this chain."""
    if not chain:
        return 2.0

    chain_lower = chain.lower()
    rankings = _get_chain_momentum_rankings()

    if not rankings:
        return 2.0

    rank = rankings.get(chain_lower)
    if rank is None:
        return 2.0
    if rank == 1:
        return 10.0
    if rank == 2:
        return 7.0
    if rank == 3:
        return 4.0
    return 2.0


# ===================================================================
# Internal helpers
# ===================================================================

def _get_chain_momentum_rankings() -> dict:
    """Return {chain_lower: rank} mapping, cached for 5 minutes."""
    global _chain_momentum_cache

    now = time.monotonic()
    if _chain_momentum_cache["data"] and (now - _chain_momentum_cache["ts"]) < _CHAIN_MOMENTUM_TTL:
        return _chain_momentum_cache["data"]

    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT LOWER(chain) AS chain, COUNT(*) AS cnt "
                "FROM signals "
                "WHERE runner_alerted = 1 "
                "  AND original_timestamp >= datetime('now', '-7 days') "
                "GROUP BY LOWER(chain) "
                "ORDER BY cnt DESC"
            ).fetchall()
    except Exception as exc:
        logger.warning("chain_momentum query error: %s", exc)
        return {}

    rankings: dict[str, int] = {}
    for idx, row in enumerate(rows, start=1):
        rankings[row["chain"]] = idx

    _chain_momentum_cache = {"data": rankings, "ts": now}
    return rankings
