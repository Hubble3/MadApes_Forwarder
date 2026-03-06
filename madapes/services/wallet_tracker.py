"""Smart money wallet tracker - monitors watched wallets for cross-referencing with signals."""
import logging
from typing import List, Optional

from db import get_connection
from utils import utcnow_iso

logger = logging.getLogger(__name__)


def _ensure_wallets_table():
    """Create watched_wallets table if it doesn't exist."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watched_wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address TEXT NOT NULL,
                chain TEXT NOT NULL,
                label TEXT,
                wallet_type TEXT DEFAULT 'smart_money',
                is_active INTEGER DEFAULT 1,
                total_trades INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                avg_return REAL DEFAULT 0.0,
                added_at TEXT,
                last_activity_at TEXT,
                UNIQUE(address, chain)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_id INTEGER NOT NULL,
                token_address TEXT NOT NULL,
                chain TEXT NOT NULL,
                action TEXT NOT NULL,
                amount REAL,
                price_at_action REAL,
                timestamp TEXT NOT NULL,
                signal_id INTEGER,
                FOREIGN KEY (wallet_id) REFERENCES watched_wallets(id)
            )
        """)
        conn.commit()


def add_wallet(address: str, chain: str, label: str = "", wallet_type: str = "smart_money") -> Optional[int]:
    """Add a wallet to watch list. Returns wallet ID or None if duplicate."""
    _ensure_wallets_table()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO watched_wallets (address, chain, label, wallet_type, added_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (address.lower(), chain.lower(), label, wallet_type, utcnow_iso()),
            )
            conn.commit()
            row = conn.execute(
                "SELECT id FROM watched_wallets WHERE address = ? AND chain = ?",
                (address.lower(), chain.lower()),
            ).fetchone()
            return row["id"] if row else None
    except Exception as e:
        logger.error(f"Error adding wallet: {e}")
        return None


def remove_wallet(address: str, chain: str) -> bool:
    """Remove a wallet from watch list."""
    _ensure_wallets_table()
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM watched_wallets WHERE address = ? AND chain = ?",
                (address.lower(), chain.lower()),
            )
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing wallet: {e}")
        return False


def get_watched_wallets(chain: Optional[str] = None, active_only: bool = True) -> list:
    """Get all watched wallets, optionally filtered by chain."""
    _ensure_wallets_table()
    with get_connection() as conn:
        if chain:
            query = "SELECT * FROM watched_wallets WHERE chain = ?"
            params = [chain.lower()]
        else:
            query = "SELECT * FROM watched_wallets WHERE 1=1"
            params = []
        if active_only:
            query += " AND is_active = 1"
        query += " ORDER BY added_at DESC"
        return conn.execute(query, params).fetchall()


def record_wallet_transaction(
    wallet_id: int, token_address: str, chain: str,
    action: str, amount: float = 0.0, price_at_action: float = 0.0,
    signal_id: Optional[int] = None,
):
    """Record a wallet transaction (buy/sell)."""
    _ensure_wallets_table()
    try:
        with get_connection() as conn:
            conn.execute(
                """INSERT INTO wallet_transactions
                   (wallet_id, token_address, chain, action, amount, price_at_action, timestamp, signal_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (wallet_id, token_address.lower(), chain.lower(), action,
                 amount, price_at_action, utcnow_iso(), signal_id),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error recording wallet transaction: {e}")


def check_wallet_overlap(token_address: str, chain: str) -> List[dict]:
    """Check if any watched wallets have interacted with this token.
    Returns list of matching wallet info dicts.
    """
    _ensure_wallets_table()
    try:
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT w.address, w.label, w.wallet_type, wt.action, wt.timestamp
                   FROM wallet_transactions wt
                   JOIN watched_wallets w ON w.id = wt.wallet_id
                   WHERE wt.token_address = ? AND wt.chain = ?
                   ORDER BY wt.timestamp DESC
                   LIMIT 10""",
                (token_address.lower(), chain.lower()),
            ).fetchall()
            return [
                {
                    "wallet_address": r["address"],
                    "label": r["label"],
                    "wallet_type": r["wallet_type"],
                    "action": r["action"],
                    "timestamp": r["timestamp"],
                }
                for r in rows
            ]
    except Exception as e:
        logger.error(f"Error checking wallet overlap: {e}")
        return []
