"""Pattern recognition service - detects common token patterns."""
import logging
from typing import List, Optional

from madapes.formatting import safe_float

logger = logging.getLogger(__name__)


def detect_patterns(signal_data: dict, current_data: Optional[dict] = None) -> List[str]:
    """Detect trading patterns from signal and current market data.

    Returns list of pattern strings detected.
    """
    patterns = []

    original_price = safe_float(signal_data.get("original_price"))
    original_mc = safe_float(signal_data.get("original_market_cap"))
    original_liq = safe_float(signal_data.get("original_liquidity"))
    original_vol = safe_float(signal_data.get("original_volume"))

    if not current_data:
        # Static analysis only
        if original_mc and original_mc < 10_000:
            patterns.append("micro_launch")
        if original_liq and original_mc and original_liq > 0:
            liq_ratio = original_liq / original_mc if original_mc > 0 else 0
            if liq_ratio < 0.02:
                patterns.append("low_liq_ratio")
        return patterns

    current_price = safe_float(current_data.get("price"))
    current_mc = safe_float(current_data.get("fdv"))
    current_liq = safe_float(current_data.get("liquidity"))
    volume_5m = safe_float(current_data.get("volume_5m"))
    volume_1h = safe_float(current_data.get("volume_1h"))
    volume_24h = safe_float(current_data.get("volume_24h"))
    price_change_5m = safe_float(current_data.get("price_change_5m"), 0)
    price_change_1h = safe_float(current_data.get("price_change_1h"), 0)

    if not current_price or not original_price:
        return patterns

    price_change_total = ((current_price - original_price) / original_price) * 100 if original_price > 0 else 0

    # Pump-and-dump detection
    max_price = safe_float(signal_data.get("max_price_seen"))
    if max_price and max_price > 0 and current_price:
        drawdown = ((max_price - current_price) / max_price) * 100
        peak_gain = ((max_price - original_price) / original_price) * 100 if original_price > 0 else 0
        if peak_gain > 100 and drawdown > 60:
            patterns.append("pump_and_dump")
        elif peak_gain > 50 and drawdown > 40:
            patterns.append("possible_dump")

    # Organic breakout: steady climb with volume
    if price_change_total > 30 and price_change_5m > 0 and price_change_1h > 0:
        if volume_1h and volume_24h and volume_24h > 0:
            vol_ratio = (volume_1h * 24) / volume_24h
            if 0.5 < vol_ratio < 3.0:
                patterns.append("organic_breakout")

    # Liquidity drain
    if original_liq and current_liq and original_liq > 0:
        liq_change = ((current_liq - original_liq) / original_liq) * 100
        if liq_change < -50:
            patterns.append("liquidity_drain")
        elif liq_change < -30:
            patterns.append("liquidity_declining")

    # Wash trading detection (high volume relative to MC with flat price)
    if volume_24h and current_mc and current_mc > 0:
        vol_mc_ratio = volume_24h / current_mc
        if vol_mc_ratio > 5.0 and abs(price_change_1h) < 5:
            patterns.append("possible_wash_trading")

    # Volume spike
    if volume_5m and volume_1h and volume_1h > 0:
        avg_5m = volume_1h / 12.0
        if avg_5m > 0 and volume_5m > avg_5m * 5:
            patterns.append("volume_spike")

    # Momentum continuation
    if price_change_5m > 5 and price_change_1h > 10 and price_change_total > 20:
        patterns.append("momentum_continuation")

    # Reversal
    if price_change_total > 20 and price_change_5m < -5:
        patterns.append("possible_reversal")

    return patterns


def pattern_risk_level(patterns: List[str]) -> str:
    """Assess overall risk level from detected patterns."""
    high_risk = {"pump_and_dump", "liquidity_drain", "possible_wash_trading"}
    medium_risk = {"possible_dump", "liquidity_declining", "possible_reversal", "low_liq_ratio"}

    if any(p in high_risk for p in patterns):
        return "HIGH"
    if any(p in medium_risk for p in patterns):
        return "MEDIUM"
    return "LOW"
