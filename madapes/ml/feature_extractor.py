"""Feature extraction for ML models from signal data."""
import logging
from typing import Optional

from madapes.formatting import safe_float

logger = logging.getLogger(__name__)

# Feature names for the ML pipeline
FEATURE_NAMES = [
    "original_price",
    "original_volume",
    "original_liquidity",
    "original_market_cap",
    "hour_utc",
    "day_of_week",
    "is_asia_session",
    "is_eu_session",
    "is_us_session",
    "chain_ethereum",
    "chain_solana",
    "chain_bsc",
    "chain_base",
    "chain_arbitrum",
    "chain_other",
    "log_market_cap",
    "log_liquidity",
    "liq_to_mc_ratio",
    "vol_to_mc_ratio",
    "caller_score",
    "caller_win_rate",
    "caller_signal_count",
    "multi_caller_count",
    "is_runner",
]


def extract_features(signal_row, caller_data=None, multi_caller_count=1) -> Optional[list]:
    """Extract feature vector from a signal row.

    Returns a list of float values matching FEATURE_NAMES, or None if essential data is missing.
    """
    import math

    original_price = safe_float(signal_row.get("original_price"))
    original_volume = safe_float(signal_row.get("original_volume"), 0)
    original_liquidity = safe_float(signal_row.get("original_liquidity"), 0)
    original_market_cap = safe_float(signal_row.get("original_market_cap"))

    if original_price is None or original_market_cap is None:
        return None

    hour_utc = signal_row.get("hour_utc") or 0
    day_of_week = signal_row.get("day_of_week") or 0
    session = (signal_row.get("session") or "").lower()
    chain = (signal_row.get("chain") or "").lower()

    # Session one-hot
    is_asia = 1.0 if session == "asia" else 0.0
    is_eu = 1.0 if session == "eu" else 0.0
    is_us = 1.0 if session == "us" else 0.0

    # Chain one-hot
    chain_ethereum = 1.0 if chain == "ethereum" else 0.0
    chain_solana = 1.0 if chain == "solana" else 0.0
    chain_bsc = 1.0 if chain == "bsc" else 0.0
    chain_base = 1.0 if chain == "base" else 0.0
    chain_arbitrum = 1.0 if chain == "arbitrum" else 0.0
    chain_other = 1.0 if chain not in ("ethereum", "solana", "bsc", "base", "arbitrum") else 0.0

    # Log-transformed features
    log_mc = math.log10(max(original_market_cap, 1))
    log_liq = math.log10(max(original_liquidity, 1)) if original_liquidity else 0

    # Ratios
    liq_mc_ratio = (original_liquidity / original_market_cap) if original_market_cap > 0 and original_liquidity else 0
    vol_mc_ratio = (original_volume / original_market_cap) if original_market_cap > 0 and original_volume else 0

    # Caller features
    caller_score = 50.0
    caller_wr = 0.5
    caller_count = 0
    if caller_data:
        caller_score = caller_data.get("composite_score", 50)
        total = caller_data.get("win_count", 0) + caller_data.get("loss_count", 0)
        caller_wr = (caller_data.get("win_count", 0) / total) if total > 0 else 0.5
        caller_count = caller_data.get("total_signals", 0)

    is_runner = 1.0 if signal_row.get("runner_alerted") else 0.0

    return [
        original_price,
        original_volume or 0,
        original_liquidity or 0,
        original_market_cap,
        float(hour_utc),
        float(day_of_week),
        is_asia,
        is_eu,
        is_us,
        chain_ethereum,
        chain_solana,
        chain_bsc,
        chain_base,
        chain_arbitrum,
        chain_other,
        log_mc,
        log_liq,
        liq_mc_ratio,
        vol_mc_ratio,
        caller_score,
        caller_wr,
        float(caller_count),
        float(multi_caller_count),
        is_runner,
    ]


def extract_label(signal_row) -> Optional[float]:
    """Extract target label from a signal row.

    Returns 1.0 for win, 0.0 for loss, None for active/unchecked.
    """
    status = signal_row.get("status")
    if status == "win":
        return 1.0
    elif status == "loss":
        return 0.0
    return None


def extract_return(signal_row) -> Optional[float]:
    """Extract return percentage for regression target."""
    pct = safe_float(signal_row.get("price_change_percent"))
    return pct
