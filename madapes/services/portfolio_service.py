"""Portfolio service - virtual portfolio tracking with P&L computation."""
import logging
from typing import List, Optional

from db import get_connection
from madapes.formatting import safe_float
from utils import utcnow_iso

logger = logging.getLogger(__name__)

DEFAULT_POSITION_SIZE = 100.0  # $100 virtual per signal


def _ensure_portfolio_table():
    """Create portfolio_entries table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS portfolio_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER NOT NULL UNIQUE,
                token_address TEXT NOT NULL,
                chain TEXT NOT NULL,
                token_name TEXT,
                token_symbol TEXT,
                sender_id INTEGER,
                sender_name TEXT,
                entry_price REAL NOT NULL,
                current_price REAL,
                peak_price REAL,
                position_size REAL DEFAULT 100.0,
                unrealized_pnl REAL DEFAULT 0.0,
                unrealized_pnl_pct REAL DEFAULT 0.0,
                realized_pnl REAL,
                realized_pnl_pct REAL,
                max_drawdown_pct REAL DEFAULT 0.0,
                status TEXT DEFAULT 'open',
                entry_timestamp TEXT NOT NULL,
                exit_timestamp TEXT,
                exit_price REAL,
                updated_at TEXT
            )
        """)
        conn.commit()


def open_position(
    signal_id: int,
    token_address: str,
    chain: str,
    entry_price: float,
    token_name: str = "",
    token_symbol: str = "",
    sender_id: Optional[int] = None,
    sender_name: str = "",
    position_size: float = DEFAULT_POSITION_SIZE,
) -> Optional[int]:
    """Open a new virtual position when a signal is forwarded."""
    if not entry_price or entry_price <= 0:
        return None
    _ensure_portfolio_table()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO portfolio_entries
                   (signal_id, token_address, chain, token_name, token_symbol,
                    sender_id, sender_name, entry_price, current_price, peak_price,
                    position_size, status, entry_timestamp, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?)""",
                (signal_id, token_address, chain, token_name, token_symbol,
                 sender_id, sender_name, entry_price, entry_price, entry_price,
                 position_size, utcnow_iso(), utcnow_iso()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM portfolio_entries WHERE signal_id = ?", (signal_id,)
            ).fetchone()
            return row["id"] if row else None
    except Exception as e:
        logger.error(f"Error opening position for signal {signal_id}: {e}")
        return None


def update_position(signal_id: int, current_price: float):
    """Update position with current price, recompute P&L and drawdown."""
    if not current_price or current_price <= 0:
        return
    _ensure_portfolio_table()
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_entries WHERE signal_id = ? AND status = 'open'",
                (signal_id,),
            ).fetchone()
            if not row:
                return

            entry_price = row["entry_price"]
            peak_price = row["peak_price"] if row["peak_price"] is not None else entry_price
            position_size = row["position_size"]

            # Update peak
            new_peak = max(peak_price, current_price)

            # P&L
            pnl_pct = ((current_price - entry_price) / entry_price) * 100
            pnl_usd = position_size * (pnl_pct / 100)

            # Drawdown from peak
            drawdown_pct = ((new_peak - current_price) / new_peak) * 100 if new_peak > 0 else 0
            max_drawdown = max(row["max_drawdown_pct"] or 0, drawdown_pct)

            conn.execute(
                """UPDATE portfolio_entries SET
                   current_price = ?, peak_price = ?,
                   unrealized_pnl = ?, unrealized_pnl_pct = ?,
                   max_drawdown_pct = ?, updated_at = ?
                   WHERE signal_id = ? AND status = 'open'""",
                (current_price, new_peak, round(pnl_usd, 2), round(pnl_pct, 2),
                 round(max_drawdown, 2), utcnow_iso(), signal_id),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating position for signal {signal_id}: {e}")


def close_position(signal_id: int, exit_price: float):
    """Close a position at exit_price, compute realized P&L."""
    if not exit_price or exit_price <= 0:
        return
    _ensure_portfolio_table()
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM portfolio_entries WHERE signal_id = ? AND status = 'open'",
                (signal_id,),
            ).fetchone()
            if not row:
                return

            entry_price = row["entry_price"]
            position_size = row["position_size"]

            pnl_pct = ((exit_price - entry_price) / entry_price) * 100
            pnl_usd = position_size * (pnl_pct / 100)

            conn.execute(
                """UPDATE portfolio_entries SET
                   current_price = ?, exit_price = ?,
                   realized_pnl = ?, realized_pnl_pct = ?,
                   unrealized_pnl = 0, unrealized_pnl_pct = 0,
                   status = 'closed', exit_timestamp = ?, updated_at = ?
                   WHERE signal_id = ? AND status = 'open'""",
                (exit_price, exit_price, round(pnl_usd, 2), round(pnl_pct, 2),
                 utcnow_iso(), utcnow_iso(), signal_id),
            )
            conn.commit()
            logger.debug(f"Closed position for signal {signal_id}: {pnl_pct:+.1f}%")
    except Exception as e:
        logger.error(f"Error closing position for signal {signal_id}: {e}")


def get_open_positions() -> list:
    """Get all open positions."""
    _ensure_portfolio_table()
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM portfolio_entries WHERE status = 'open' ORDER BY entry_timestamp DESC"
        ).fetchall()


def get_closed_positions(limit: int = 50) -> list:
    """Get recently closed positions."""
    _ensure_portfolio_table()
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM portfolio_entries WHERE status = 'closed' ORDER BY exit_timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()


def get_portfolio_summary() -> dict:
    """Compute aggregate portfolio metrics."""
    _ensure_portfolio_table()
    with get_connection() as conn:
        open_rows = conn.execute(
            "SELECT * FROM portfolio_entries WHERE status = 'open'"
        ).fetchall()
        closed_rows = conn.execute(
            "SELECT * FROM portfolio_entries WHERE status = 'closed'"
        ).fetchall()

    total_open = len(open_rows)
    total_closed = len(closed_rows)

    # Open positions aggregate
    total_unrealized = sum(safe_float(r["unrealized_pnl"], 0) for r in open_rows)
    total_invested_open = sum(safe_float(r["position_size"], 0) for r in open_rows)

    # Closed positions aggregate
    total_realized = sum(safe_float(r["realized_pnl"], 0) for r in closed_rows)
    wins = sum(1 for r in closed_rows if (r["realized_pnl"] or 0) > 0)
    losses = sum(1 for r in closed_rows if (r["realized_pnl"] or 0) <= 0)
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0

    # Best/worst
    if closed_rows:
        best_pnl_pct = max(safe_float(r["realized_pnl_pct"], 0) for r in closed_rows)
        worst_pnl_pct = min(safe_float(r["realized_pnl_pct"], 0) for r in closed_rows)
    else:
        best_pnl_pct = 0
        worst_pnl_pct = 0

    # Aggregate drawdown
    all_drawdowns = [safe_float(r["max_drawdown_pct"], 0) for r in open_rows + closed_rows]
    max_drawdown = max(all_drawdowns) if all_drawdowns else 0

    return {
        "total_open": total_open,
        "total_closed": total_closed,
        "total_unrealized_pnl": round(total_unrealized, 2),
        "total_realized_pnl": round(total_realized, 2),
        "total_pnl": round(total_unrealized + total_realized, 2),
        "total_invested_open": round(total_invested_open, 2),
        "win_rate": round(win_rate, 1),
        "wins": wins,
        "losses": losses,
        "best_pnl_pct": round(best_pnl_pct, 2),
        "worst_pnl_pct": round(worst_pnl_pct, 2),
        "max_drawdown_pct": round(max_drawdown, 2),
    }


def get_portfolio_by_sender(sender_id: int) -> dict:
    """Get portfolio summary for a specific caller."""
    _ensure_portfolio_table()
    with get_connection() as conn:
        closed = conn.execute(
            "SELECT * FROM portfolio_entries WHERE sender_id = ? AND status = 'closed'",
            (sender_id,),
        ).fetchall()
        open_positions = conn.execute(
            "SELECT * FROM portfolio_entries WHERE sender_id = ? AND status = 'open'",
            (sender_id,),
        ).fetchall()

    total_realized = sum(safe_float(r["realized_pnl"], 0) for r in closed)
    total_unrealized = sum(safe_float(r["unrealized_pnl"], 0) for r in open_positions)
    wins = sum(1 for r in closed if (r["realized_pnl"] or 0) > 0)
    total_closed = len(closed)

    return {
        "sender_id": sender_id,
        "total_positions": total_closed + len(open_positions),
        "open_positions": len(open_positions),
        "closed_positions": total_closed,
        "total_realized_pnl": round(total_realized, 2),
        "total_unrealized_pnl": round(total_unrealized, 2),
        "win_rate": round((wins / total_closed * 100) if total_closed > 0 else 0, 1),
    }


def get_portfolio_by_chain() -> dict:
    """Get portfolio P&L broken down by chain."""
    _ensure_portfolio_table()
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT chain,
                      COUNT(*) as total,
                      SUM(CASE WHEN status='closed' AND realized_pnl > 0 THEN 1 ELSE 0 END) as wins,
                      SUM(CASE WHEN status='closed' THEN 1 ELSE 0 END) as closed,
                      SUM(COALESCE(realized_pnl, 0)) as total_realized,
                      SUM(COALESCE(unrealized_pnl, 0)) as total_unrealized
               FROM portfolio_entries
               GROUP BY chain
               ORDER BY SUM(COALESCE(realized_pnl, 0) + COALESCE(unrealized_pnl, 0)) DESC"""
        ).fetchall()

    result = {}
    for r in rows:
        chain = r["chain"] or "unknown"
        closed_count = r["closed"] or 0
        result[chain] = {
            "total": r["total"],
            "wins": r["wins"] or 0,
            "closed": closed_count,
            "win_rate": round((r["wins"] / closed_count * 100) if closed_count > 0 else 0, 1),
            "total_realized": round(r["total_realized"] or 0, 2),
            "total_unrealized": round(r["total_unrealized"] or 0, 2),
        }
    return result
