"""Signal confidence scoring service - computes composite confidence for each signal."""
import logging
from datetime import datetime
from typing import Optional

from madapes.services.caller_service import get_caller_score

logger = logging.getLogger(__name__)

# Score weights (total = 100)
W_CALLER = 30       # Caller track record
W_LIQUIDITY = 15    # Liquidity depth
W_MC_RANGE = 15     # Market cap sweet spot
W_CHAIN = 10        # Chain reliability
W_TIME_OF_DAY = 10  # Historical time-of-day performance
W_MULTI_SOURCE = 20 # Multi-caller / multi-source bonus

# Chain base scores (based on ecosystem maturity and rug frequency)
CHAIN_SCORES = {
    "ethereum": 1.0,
    "base": 0.8,
    "arbitrum": 0.8,
    "polygon": 0.7,
    "optimism": 0.7,
    "bsc": 0.5,
    "solana": 0.6,
}

# MC sweet spot: tokens in $50K-$5M range historically perform best for early signals
MC_SWEET_SPOT_MIN = 50_000
MC_SWEET_SPOT_MAX = 5_000_000

# Liquidity thresholds
LIQ_MIN_GOOD = 10_000      # $10K minimum for decent liquidity
LIQ_IDEAL = 100_000        # $100K+ is strong


def _caller_component(sender_id: Optional[int]) -> float:
    """Caller score component (0-1). Based on caller's composite score."""
    if sender_id is None:
        return 0.3  # Unknown caller gets neutral score
    score = get_caller_score(sender_id)
    if score <= 0:
        return 0.3  # No data = neutral
    return min(score / 100.0, 1.0)


def _mc_range_component(market_cap: Optional[float]) -> float:
    """Market cap range component (0-1). Sweet spot scoring."""
    if market_cap is None or market_cap <= 0:
        return 0.3  # Unknown MC
    if MC_SWEET_SPOT_MIN <= market_cap <= MC_SWEET_SPOT_MAX:
        return 1.0
    if market_cap < MC_SWEET_SPOT_MIN:
        # Below sweet spot - still okay but riskier (very micro)
        return max(0.2, market_cap / MC_SWEET_SPOT_MIN)
    # Above sweet spot - diminishing returns for signal alpha
    # $5M = 1.0, $50M = 0.5, $500M = 0.2
    import math
    ratio = market_cap / MC_SWEET_SPOT_MAX
    return max(0.2, 1.0 / (1.0 + math.log10(ratio)))


def _liquidity_component(liquidity: Optional[float]) -> float:
    """Liquidity component (0-1). Higher liquidity = safer exit."""
    if liquidity is None or liquidity <= 0:
        return 0.1  # No liquidity data = very risky
    if liquidity >= LIQ_IDEAL:
        return 1.0
    if liquidity >= LIQ_MIN_GOOD:
        return 0.5 + 0.5 * ((liquidity - LIQ_MIN_GOOD) / (LIQ_IDEAL - LIQ_MIN_GOOD))
    # Below minimum - risky
    return max(0.1, 0.5 * (liquidity / LIQ_MIN_GOOD))


def _chain_component(chain: Optional[str]) -> float:
    """Chain component (0-1). Based on ecosystem maturity."""
    if not chain:
        return 0.5
    return CHAIN_SCORES.get(chain.lower(), 0.5)


def _time_of_day_component(timestamp: Optional[str]) -> float:
    """Time-of-day component (0-1). US/EU market hours score higher."""
    if not timestamp:
        return 0.5
    try:
        ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        hour_utc = ts.hour
        # Peak crypto trading: 13-21 UTC (US morning through EU evening)
        if 13 <= hour_utc <= 21:
            return 1.0
        # Decent: 8-13 UTC (EU morning) and 21-24 UTC (US afternoon)
        if 8 <= hour_utc < 13 or 21 < hour_utc <= 23:
            return 0.7
        # Off-peak: 0-8 UTC
        return 0.4
    except Exception:
        return 0.5


def compute_signal_confidence(
    sender_id: Optional[int] = None,
    market_cap: Optional[float] = None,
    liquidity: Optional[float] = None,
    chain: Optional[str] = None,
    timestamp: Optional[str] = None,
    multi_source_count: int = 1,
) -> float:
    """Compute composite signal confidence score (0-100).

    Components:
    - Caller score (30pts): track record of the signal sender
    - MC range (15pts): market cap in sweet spot
    - Liquidity (15pts): exit safety
    - Chain (10pts): ecosystem maturity
    - Time of day (10pts): market hours bonus
    - Multi-source (20pts): multiple callers = high conviction
    """
    caller_pts = _caller_component(sender_id) * W_CALLER
    mc_pts = _mc_range_component(market_cap) * W_MC_RANGE
    liq_pts = _liquidity_component(liquidity) * W_LIQUIDITY
    chain_pts = _chain_component(chain) * W_CHAIN
    time_pts = _time_of_day_component(timestamp) * W_TIME_OF_DAY

    # Multi-source bonus: 1 caller = 0pts, 2 = 12pts, 3+ = 20pts
    if multi_source_count >= 3:
        multi_pts = W_MULTI_SOURCE
    elif multi_source_count == 2:
        multi_pts = W_MULTI_SOURCE * 0.6
    else:
        multi_pts = 0.0

    total = caller_pts + mc_pts + liq_pts + chain_pts + time_pts + multi_pts
    return min(round(total, 1), 100.0)


def confidence_label(score: float) -> str:
    """Return a short label for a confidence score."""
    if score >= 80:
        return "HIGH"
    elif score >= 55:
        return "MEDIUM"
    elif score >= 30:
        return "LOW"
    else:
        return "VERY LOW"


def confidence_badge(score: float) -> str:
    """Return an HTML badge for the confidence score."""
    label = confidence_label(score)
    return f"<b>[{label} {score:.0f}]</b>"
