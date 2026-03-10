"""Runtime settings that can be updated from the dashboard.

Reads from bot_settings DB table (set via dashboard API), falls back to config.py defaults.
Values are read fresh on every call so changes take effect immediately without restart.
"""
import json
import logging

import config
from db import get_connection

logger = logging.getLogger(__name__)

# Cache to avoid DB reads on every single call — refreshes every N seconds
_cache = {}
_cache_ts = 0
_CACHE_TTL = 10  # seconds


def _load_overrides() -> dict:
    """Load all runtime overrides from bot_settings table."""
    import time
    global _cache, _cache_ts
    now = time.time()
    if now - _cache_ts < _CACHE_TTL and _cache:
        return _cache
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM bot_settings").fetchall()
            _cache = {row["key"]: row["value"] for row in rows}
            _cache_ts = now
    except Exception:
        pass
    return _cache


def _get(key: str, default, cast=float):
    """Get a setting value: DB override > config default."""
    overrides = _load_overrides()
    if key in overrides:
        try:
            return cast(overrides[key])
        except (ValueError, TypeError):
            pass
    return default


def get_mc_threshold() -> float:
    return _get("mc_threshold", config.MC_THRESHOLD, float)


def get_min_market_cap() -> float:
    return _get("min_market_cap", config.MIN_MARKET_CAP, float)


def get_forward_delay() -> float:
    return _get("forward_delay", config.FORWARD_DELAY, float)


def get_max_signals() -> int:
    return _get("max_signals", config.MAX_SIGNALS, int)


def get_runner_velocity_min() -> float:
    return _get("runner_velocity_min", config.RUNNER_VELOCITY_MIN, float)


def get_runner_vol_accel_min() -> float:
    return _get("runner_vol_accel_min", config.RUNNER_VOL_ACCEL_MIN, float)


def get_runner_poll_interval() -> int:
    return _get("runner_poll_interval", config.RUNNER_POLL_INTERVAL, int)


def get_display_timezone() -> str:
    return _get("display_timezone", config.DISPLAY_TIMEZONE, str)


def get_runner_exit_drawdown_pct() -> float:
    return _get("runner_exit_drawdown_pct", config.RUNNER_EXIT_DRAWDOWN_PCT, float)


def get_runner_exit_liq_drain_pct() -> float:
    return _get("runner_exit_liq_drain_pct", config.RUNNER_EXIT_LIQ_DRAIN_PCT, float)


def get_runner_dedup_window() -> int:
    return _get("runner_dedup_window", config.RUNNER_DEDUP_WINDOW, int)


def get_source_groups() -> list:
    """Source groups can't be changed at runtime — requires bot restart to re-resolve entities."""
    return config.SOURCE_GROUPS
