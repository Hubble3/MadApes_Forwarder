"""Event definitions for MadApes Forwarder event-driven architecture."""
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List


# Channel names for Redis pub/sub
CHANNEL_SIGNAL_DETECTED = "madapes:signal:detected"
CHANNEL_SIGNAL_ENRICHED = "madapes:signal:enriched"
CHANNEL_SIGNAL_FORWARDED = "madapes:signal:forwarded"
CHANNEL_PERFORMANCE_CHECKED = "madapes:performance:checked"
CHANNEL_RUNNER_DETECTED = "madapes:runner:detected"


@dataclass
class SignalDetected:
    """Emitted when a contract address is detected in a message."""
    signal_id: int
    token_address: str
    chain: str
    sender_id: Optional[int]
    sender_name: str
    source_group: str
    message_id: int
    all_addresses: List[tuple] = field(default_factory=list)
    timestamp: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = "SignalDetected"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SignalDetected":
        d.pop("event_type", None)
        return cls(**d)


@dataclass
class SignalEnriched:
    """Emitted after DexScreener data is fetched for a signal."""
    signal_id: int
    token_address: str
    chain: str
    price: Optional[float] = None
    market_cap: Optional[float] = None
    liquidity: Optional[float] = None
    volume_24h: Optional[float] = None
    token_name: str = ""
    token_symbol: str = ""
    dexscreener_link: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = "SignalEnriched"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SignalEnriched":
        d.pop("event_type", None)
        return cls(**d)


@dataclass
class SignalForwarded:
    """Emitted after a signal is successfully forwarded to a destination."""
    signal_id: int
    token_address: str
    chain: str
    destination_type: str
    forwarded_message_id: Optional[int] = None
    market_cap: Optional[float] = None
    signal_tier: Optional[str] = None
    token_name: str = ""
    token_symbol: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = "SignalForwarded"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "SignalForwarded":
        d.pop("event_type", None)
        return cls(**d)


@dataclass
class PerformanceChecked:
    """Emitted after a 1h or 6h performance check."""
    signal_id: int
    token_address: str
    time_label: str  # "1h" or "6h"
    is_winner: bool
    price_change: float
    multiplier: float
    current_price: Optional[float] = None
    current_market_cap: Optional[float] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = "PerformanceChecked"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PerformanceChecked":
        d.pop("event_type", None)
        return cls(**d)


@dataclass
class RunnerDetected:
    """Emitted when a runner is detected."""
    signal_id: int
    token_address: str
    chain: str
    velocity: float
    vol_accel: float
    price_change_pct: float
    token_name: str = ""
    token_symbol: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["event_type"] = "RunnerDetected"
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RunnerDetected":
        d.pop("event_type", None)
        return cls(**d)
