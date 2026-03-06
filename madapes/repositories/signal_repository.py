"""Signal repository - abstracts DB operations, returns Signal models."""
import logging
from typing import Optional, List

from db import (
    get_connection,
    get_all_active_signals as _get_all_active_raw,
    get_signals_to_check_1h as _get_1h_raw,
    get_signals_to_check_6h as _get_6h_raw,
    get_signals_for_runner_check as _get_runner_raw,
    get_signal_by_id as _get_by_id_raw,
    get_winning_signals as _get_winning_raw,
)
from madapes.models import Signal, signal_from_row, signals_from_rows

logger = logging.getLogger(__name__)


def get_signal(signal_id: int) -> Optional[Signal]:
    """Get a single signal by ID."""
    row = _get_by_id_raw(signal_id)
    return signal_from_row(row)


def get_all_active() -> List[Signal]:
    """All signals with status active/win/loss."""
    return signals_from_rows(_get_all_active_raw())


def get_for_1h_check() -> List[Signal]:
    """Signals needing 1-hour check."""
    return signals_from_rows(_get_1h_raw())


def get_for_6h_check() -> List[Signal]:
    """Signals needing 6-hour check."""
    return signals_from_rows(_get_6h_raw())


def get_for_runner_check(max_age_minutes=60, min_age_minutes=2) -> List[Signal]:
    """Active signals in the runner momentum window."""
    return signals_from_rows(_get_runner_raw(max_age_minutes, min_age_minutes))


def get_winners() -> List[Signal]:
    """All winning signals."""
    return signals_from_rows(_get_winning_raw())


def get_signals_by_token(token_address: str) -> List[Signal]:
    """Get all signals for a given token address."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE token_address = ? ORDER BY created_at DESC",
            (token_address,),
        ).fetchall()
        return signals_from_rows(rows)


def get_signals_by_sender(sender_id: int, limit: int = 50) -> List[Signal]:
    """Get recent signals from a specific sender."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE sender_id = ? ORDER BY created_at DESC LIMIT ?",
            (sender_id, limit),
        ).fetchall()
        return signals_from_rows(rows)


def get_signals_by_chain(chain: str, limit: int = 50) -> List[Signal]:
    """Get recent signals for a specific chain."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE chain = ? ORDER BY created_at DESC LIMIT ?",
            (chain, limit),
        ).fetchall()
        return signals_from_rows(rows)


def get_recent_signals(limit: int = 50) -> List[Signal]:
    """Get the most recent signals."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return signals_from_rows(rows)


def count_by_status() -> dict:
    """Count signals grouped by status."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) as cnt FROM signals GROUP BY status"
        ).fetchall()
        return {row["status"]: row["cnt"] for row in rows}
