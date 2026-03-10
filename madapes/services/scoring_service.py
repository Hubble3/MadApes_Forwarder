"""Signal confidence scoring service - computes composite confidence for each signal.

Weights calibrated against real signal performance data:
- Liquidity is the strongest predictor ($0 liq = always junk)
- Solana outperforms Ethereum in our data
- Caller track record matters most for repeat callers
- Time-of-day effect is minor
"""
import logging
import math
from datetime import datetime
from typing import Optional

from madapes.services.caller_service import get_caller_score

logger = logging.getLogger(__name__)

# Score weights (total = 100) — calibrated from real performance data
W_CALLER = 25       # Caller track record (Gambles 44% WR vs T1T4N 8%)
W_LIQUIDITY = 25    # Liquidity depth — strongest single predictor
W_MC_RANGE = 20     # Market cap sweet spot (micro/tiny outperform large)
W_CHAIN = 5         # Chain — minor factor with enough data
W_TIME_OF_DAY = 5   # Time-of-day — minimal effect in our data
W_MULTI_SOURCE = 20 # Multi-caller / multi-source bonus

# Chain base scores (calibrated from real data: Solana 25% WR, Ethereum 0%)
CHAIN_SCORES = {
    "solana": 0.8,
    "base": 0.7,
    "arbitrum": 0.7,
    "ethereum": 0.4,   # 0% win rate in our data — lower confidence
    "polygon": 0.5,
    "optimism": 0.6,
    "bsc": 0.4,
}

# MC sweet spot: micro/tiny caps (<50k) had 40% WR, medium/large had 0%
MC_SWEET_SPOT_MIN = 10_000
MC_SWEET_SPOT_MAX = 100_000   # Narrowed — our best performers are small caps

# Liquidity thresholds (tightened — $0 liq was always junk)
LIQ_MINIMUM = 5_000        # Below this = near zero score
LIQ_GOOD = 15_000          # Decent exit possible
LIQ_IDEAL = 50_000         # Strong liquidity


def _caller_component(sender_id: Optional[int]) -> float:
    """Caller score component (0-1). Based on caller's composite score."""
    if sender_id is None:
        return 0.3  # Unknown caller gets neutral score
    score = get_caller_score(sender_id)
    if score <= 0:
        return 0.3  # No data = neutral
    return min(score / 100.0, 1.0)


def _mc_range_component(market_cap: Optional[float]) -> float:
    """Market cap range component (0-1). Small caps outperform in our data."""
    if market_cap is None or market_cap <= 0:
        return 0.2  # Unknown MC = risky
    if MC_SWEET_SPOT_MIN <= market_cap <= MC_SWEET_SPOT_MAX:
        return 1.0
    if market_cap < MC_SWEET_SPOT_MIN:
        # Very micro — still viable but riskier
        return max(0.3, market_cap / MC_SWEET_SPOT_MIN)
    # Above sweet spot — diminishing returns
    # $100K = 1.0, $500K = 0.6, $2M = 0.3
    ratio = market_cap / MC_SWEET_SPOT_MAX
    return max(0.15, 1.0 / (1.0 + math.log10(ratio) * 1.5))


def _liquidity_component(liquidity: Optional[float]) -> float:
    """Liquidity component (0-1). Strongest single predictor of signal quality."""
    if liquidity is None or liquidity <= 0:
        return 0.0  # No liquidity = near-certain junk
    if liquidity >= LIQ_IDEAL:
        return 1.0
    if liquidity >= LIQ_GOOD:
        return 0.6 + 0.4 * ((liquidity - LIQ_GOOD) / (LIQ_IDEAL - LIQ_GOOD))
    if liquidity >= LIQ_MINIMUM:
        return 0.3 + 0.3 * ((liquidity - LIQ_MINIMUM) / (LIQ_GOOD - LIQ_MINIMUM))
    # Below minimum — very risky
    return max(0.05, 0.3 * (liquidity / LIQ_MINIMUM))


def _chain_component(chain: Optional[str]) -> float:
    """Chain component (0-1). Based on actual win rates in our data."""
    if not chain:
        return 0.5
    return CHAIN_SCORES.get(chain.lower(), 0.5)


def _time_of_day_component(timestamp: Optional[str]) -> float:
    """Time-of-day component (0-1). Minor effect in our data."""
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

    Components (calibrated from real data):
    - Caller score (25pts): track record of the signal sender
    - Liquidity (25pts): strongest predictor — $0 liq = always junk
    - MC range (20pts): small caps outperform in our data
    - Chain (5pts): Solana >> Ethereum in our data
    - Time of day (5pts): minor effect
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
    if score >= 70:
        return "HIGH"
    elif score >= 45:
        return "MEDIUM"
    elif score >= 25:
        return "LOW"
    else:
        return "VERY LOW"


def confidence_badge(score: float) -> str:
    """Return an HTML badge for the confidence score."""
    label = confidence_label(score)
    return f"<b>[{label} {score:.0f}]</b>"
