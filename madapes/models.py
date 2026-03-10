"""Data models for MadApes Forwarder."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Signal:
    """Represents a detected trading signal."""
    id: int = 0
    original_message_id: int = 0
    forwarded_message_id: Optional[int] = None
    token_address: str = ""
    token_type: str = "contract"
    chain: str = ""
    ticker: str = ""
    original_price: Optional[float] = None
    original_volume: Optional[float] = None
    original_liquidity: Optional[float] = None
    original_market_cap: Optional[float] = None
    original_timestamp: str = ""
    sender_id: Optional[int] = None
    sender_name: str = ""
    source_group: str = ""
    status: str = "active"
    checked_1h: int = 0
    checked_6h: int = 0
    last_check_timestamp: Optional[str] = None
    current_price: Optional[float] = None
    current_volume: Optional[float] = None
    current_liquidity: Optional[float] = None
    current_market_cap: Optional[float] = None
    price_change_percent: Optional[float] = None
    multiplier: Optional[float] = None
    created_at: Optional[str] = None
    token_name: Optional[str] = None
    token_symbol: Optional[str] = None
    checked_1h_at: Optional[str] = None
    checked_6h_at: Optional[str] = None
    price_1h: Optional[float] = None
    market_cap_1h: Optional[float] = None
    price_change_1h: Optional[float] = None
    multiplier_1h: Optional[float] = None
    price_6h: Optional[float] = None
    market_cap_6h: Optional[float] = None
    price_change_6h: Optional[float] = None
    multiplier_6h: Optional[float] = None
    original_dexscreener_link: Optional[str] = None
    signal_link: Optional[str] = None
    runner_alerted: int = 0
    runner_alerted_at: Optional[str] = None
    max_price_seen: Optional[float] = None
    max_price_seen_at: Optional[str] = None
    max_market_cap_seen: Optional[float] = None
    max_market_cap_seen_at: Optional[str] = None
    original_dex_id: Optional[str] = None
    destination_type: Optional[str] = None
    hour_utc: Optional[int] = None
    day_of_week: Optional[int] = None
    session: Optional[str] = None
    outcome: Optional[str] = None


@dataclass
class Caller:
    """Represents a signal caller (sender) with scoring data."""
    sender_id: int = 0
    sender_name: str = ""
    total_signals: int = 0
    win_count: int = 0
    loss_count: int = 0
    runner_count: int = 0
    avg_return: float = 0.0
    best_return: float = 0.0
    worst_return: float = 0.0
    composite_score: float = 0.0  # 0-100
    last_signal_at: Optional[str] = None
    big_win_count: int = 0
    runner_rate: float = 0.0
    big_win_rate: float = 0.0
    best_chain: Optional[str] = None


@dataclass
class PortfolioEntry:
    """Represents a virtual portfolio position."""
    id: int = 0
    signal_id: int = 0
    token_address: str = ""
    chain: str = ""
    entry_price: float = 0.0
    current_price: Optional[float] = None
    peak_price: Optional[float] = None
    position_size: float = 100.0  # virtual $100 per signal
    unrealized_pnl: Optional[float] = None
    realized_pnl: Optional[float] = None
    status: str = "open"  # open, closed
    entry_timestamp: str = ""
    exit_timestamp: Optional[str] = None
    exit_price: Optional[float] = None


def signal_from_row(row) -> Signal:
    """Convert a sqlite3.Row to a Signal model."""
    if row is None:
        return None
    keys = row.keys()
    kwargs = {}
    for key in keys:
        if hasattr(Signal, key):
            kwargs[key] = row[key]
    return Signal(**kwargs)


def signals_from_rows(rows) -> list:
    """Convert a list of sqlite3.Row to Signal models."""
    return [signal_from_row(r) for r in rows if r is not None]
