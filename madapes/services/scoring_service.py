"""Signal confidence scoring service - computes composite confidence for each signal.

Weights calibrated against real signal performance data (n=24):
- Market cap is the STRONGEST predictor: <10k = 100% WR, 100k+ = 0% WR
- High liquidity/volume actually correlate with LOSSES (bigger MC = more liq)
- $0 liquidity is NOT a death sentence (4/6 winners had $0 liq at detection)
- Callers are similar (~30% WR each) — not a differentiator yet
- Chain: only Solana has wins; Ethereum = 0% WR
- 15m early momentum is a strong signal when available
"""
import logging
import math
from datetime import datetime
from typing import Optional

from madapes.services.caller_service import get_caller_score

logger = logging.getLogger(__name__)

# Score weights (total = 100) — calibrated from real performance data
W_MC_RANGE = 35      # Market cap is the #1 predictor by far
W_CALLER = 15        # Callers are similar (~30% WR) — minor differentiator
W_LIQUIDITY = 10     # Tricky: high liq correlates with LOSSES, but $0 is risky
W_CHAIN = 10         # Solana 32% WR, Ethereum 0% — meaningful
W_TIME_OF_DAY = 5    # Minimal effect
W_MULTI_SOURCE = 25  # Multi-caller = high conviction (theoretical, few examples)

# Chain base scores (calibrated: Solana 32% WR, Ethereum 0%)
CHAIN_SCORES = {
    "solana": 0.9,
    "base": 0.6,
    "arbitrum": 0.6,
    "ethereum": 0.2,   # 0% WR in our data
    "polygon": 0.4,
    "optimism": 0.5,
    "bsc": 0.3,
}

# MC sweet spot: <10k = 100% WR, 10k-50k = 31% WR, 50k-100k = 25%, 100k+ = 0%
MC_MICRO_MAX = 10_000      # 100% WR in our data
MC_SMALL_MAX = 50_000      # 31% WR
MC_MEDIUM_MAX = 100_000    # 25% WR
# Above 100k = 0% WR

# Liquidity: NOT a simple "more is better" — $0 liq winners exist
# But very high liq ($50k+) correlates with high MC (= losers)
LIQ_SWEET_MIN = 3_000      # Some liquidity = can exit
LIQ_SWEET_MAX = 30_000     # Above this = usually high MC = lower WR


def _caller_component(sender_id: Optional[int]) -> float:
    """Caller score component (0-1). Based on caller's composite score."""
    if sender_id is None:
        return 0.3  # Unknown caller gets neutral score
    score = get_caller_score(sender_id)
    if score <= 0:
        return 0.3  # No data = neutral
    return min(score / 100.0, 1.0)


def _mc_range_component(market_cap: Optional[float]) -> float:
    """Market cap range component (0-1).

    Our data: <10k = 100% WR, 10k-50k = 31%, 50k-100k = 25%, 100k+ = 0%.
    Smaller MC = higher score.
    """
    if market_cap is None or market_cap <= 0:
        return 0.5  # Unknown MC = neutral (don't penalize, could be micro)
    if market_cap <= MC_MICRO_MAX:
        return 1.0  # <$10K = best zone (100% WR)
    if market_cap <= MC_SMALL_MAX:
        # $10K-$50K: linearly scale from 0.9 to 0.7
        ratio = (market_cap - MC_MICRO_MAX) / (MC_SMALL_MAX - MC_MICRO_MAX)
        return 0.9 - ratio * 0.2
    if market_cap <= MC_MEDIUM_MAX:
        # $50K-$100K: 0.5 (25% WR — below average)
        return 0.5
    # Above $100K: 0% WR in our data — strong penalty
    # $100K = 0.25, $500K = 0.1, $1M+ = 0.05
    ratio = market_cap / MC_MEDIUM_MAX
    return max(0.05, 0.25 / math.log10(ratio + 1))


def _liquidity_component(liquidity: Optional[float]) -> float:
    """Liquidity component (0-1).

    Counterintuitive: high liquidity does NOT predict winners.
    - $0 liq: 4 winners, 6 losers (mixed — not a death sentence)
    - $5k-15k: 0W/2L
    - $15k-50k: 3W/7L (30%)
    - $50k+: 0W/2L (0%)

    We give a slight bonus for having SOME liquidity, but penalize very high.
    """
    if liquidity is None or liquidity <= 0:
        return 0.4  # $0 liq = neutral-low (not zero — winners had $0 liq)
    if liquidity <= LIQ_SWEET_MIN:
        # Very low but exists: slightly better than $0
        return 0.5
    if liquidity <= LIQ_SWEET_MAX:
        # Sweet spot: enough to exit, not so high it signals large MC
        return 0.7
    # High liquidity: correlates with large MC = losers
    # $50K = 0.4, $100K = 0.3, $250K = 0.2
    ratio = liquidity / LIQ_SWEET_MAX
    return max(0.15, 0.5 / ratio)


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

    Components (calibrated from real data, n=24):
    - MC range (35pts): THE strongest predictor — micro caps massively outperform
    - Multi-source (25pts): multiple callers = high conviction
    - Caller score (15pts): track record — callers are similar so far
    - Liquidity (10pts): NOT "more is better" — high liq = big MC = losers
    - Chain (10pts): Solana >> Ethereum
    - Time of day (5pts): minor effect
    """
    mc_pts = _mc_range_component(market_cap) * W_MC_RANGE
    caller_pts = _caller_component(sender_id) * W_CALLER
    liq_pts = _liquidity_component(liquidity) * W_LIQUIDITY
    chain_pts = _chain_component(chain) * W_CHAIN
    time_pts = _time_of_day_component(timestamp) * W_TIME_OF_DAY

    # Multi-source bonus: 1 caller = 0pts, 2 = 15pts, 3+ = 25pts
    if multi_source_count >= 3:
        multi_pts = W_MULTI_SOURCE
    elif multi_source_count == 2:
        multi_pts = W_MULTI_SOURCE * 0.6
    else:
        multi_pts = 0.0

    total = mc_pts + caller_pts + liq_pts + chain_pts + time_pts + multi_pts
    return min(round(total, 1), 100.0)


def confidence_label(score: float) -> str:
    """Return a short label for a confidence score."""
    if score >= 65:
        return "HIGH"
    elif score >= 45:
        return "MEDIUM"
    elif score >= 30:
        return "LOW"
    else:
        return "VERY LOW"


def confidence_badge(score: float) -> str:
    """Return an HTML badge for the confidence score."""
    label = confidence_label(score)
    return f"<b>[{label} {score:.0f}]</b>"
