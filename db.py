"""
Database layer for MadApes Forwarder.
All signal storage, retrieval, and updates.
Uses WAL mode, Row factory, and context managers.
"""
import logging
import sqlite3
from contextlib import contextmanager
from datetime import timedelta

from utils import utcnow_naive, utcnow_iso

logger = logging.getLogger(__name__)

DB_FILE = "signals.db"

# Runner & analytics migrations (run after base migrations)
RUNNER_ANALYTICS_MIGRATIONS = [
    ("runner_alerted", "INTEGER DEFAULT 0"),
    ("runner_alerted_at", "TEXT"),
    ("max_price_seen", "REAL"),
    ("max_price_seen_at", "TEXT"),
    ("max_market_cap_seen", "REAL"),
    ("max_market_cap_seen_at", "TEXT"),
    ("original_dex_id", "TEXT"),
    ("destination_type", "TEXT"),
    ("hour_utc", "INTEGER"),
    ("day_of_week", "INTEGER"),
    ("session", "TEXT"),
    ("outcome", "TEXT"),
    ("strategy", "TEXT"),
]


@contextmanager
def get_connection():
    """Context manager for SQLite connections with Row factory and WAL mode."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        yield conn
    finally:
        conn.close()


def init_database(max_signals=100):
    """Initialize SQLite database and run migrations."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_message_id INTEGER NOT NULL,
                forwarded_message_id INTEGER,
                token_address TEXT,
                token_type TEXT,
                chain TEXT,
                ticker TEXT,
                original_price REAL,
                original_volume REAL,
                original_liquidity REAL,
                original_market_cap REAL,
                original_timestamp TEXT NOT NULL,
                sender_id INTEGER,
                sender_name TEXT,
                source_group TEXT,
                status TEXT DEFAULT 'active',
                checked_1h INTEGER DEFAULT 0,
                checked_6h INTEGER DEFAULT 0,
                last_check_timestamp TEXT,
                current_price REAL,
                current_volume REAL,
                current_liquidity REAL,
                current_market_cap REAL,
                price_change_percent REAL,
                multiplier REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                token_name TEXT,
                token_symbol TEXT,
                checked_1h_at TEXT,
                checked_6h_at TEXT,
                price_1h REAL,
                market_cap_1h REAL,
                price_change_1h REAL,
                multiplier_1h REAL,
                price_6h REAL,
                market_cap_6h REAL,
                price_change_6h REAL,
                multiplier_6h REAL,
                original_dexscreener_link TEXT,
                signal_link TEXT,
                confidence_score REAL,
                safety_score REAL,
                tags TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_source_messages (
                source_chat_id INTEGER NOT NULL,
                source_message_id INTEGER NOT NULL,
                processed_at TEXT NOT NULL,
                PRIMARY KEY (source_chat_id, source_message_id)
            )
        """)
        cutoff = (utcnow_naive() - timedelta(days=7)).isoformat()
        cursor.execute("DELETE FROM processed_source_messages WHERE processed_at < ?", (cutoff,))

        cursor.execute("PRAGMA table_info(signals)")
        existing_cols = {row["name"] for row in cursor.fetchall()}

        base_migrations = [
            ("token_name", "TEXT"),
            ("token_symbol", "TEXT"),
            ("checked_1h_at", "TEXT"),
            ("checked_6h_at", "TEXT"),
            ("price_1h", "REAL"),
            ("market_cap_1h", "REAL"),
            ("price_change_1h", "REAL"),
            ("multiplier_1h", "REAL"),
            ("price_6h", "REAL"),
            ("market_cap_6h", "REAL"),
            ("price_change_6h", "REAL"),
            ("multiplier_6h", "REAL"),
            ("original_dexscreener_link", "TEXT"),
            ("signal_link", "TEXT"),
        ]
        for col, col_type in base_migrations:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")

        # Dashboard columns migration
        dashboard_migrations = [
            ("confidence_score", "REAL"),
            ("safety_score", "REAL"),
            ("tags", "TEXT"),
        ]
        for col, col_type in dashboard_migrations:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")

        for col, col_type in RUNNER_ANALYTICS_MIGRATIONS:
            if col not in existing_cols:
                cursor.execute(f"ALTER TABLE signals ADD COLUMN {col} {col_type}")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS analytics_daily (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL UNIQUE,
                total_signals INTEGER,
                win_count INTEGER,
                loss_count INTEGER,
                active_count INTEGER,
                runner_count INTEGER,
                best_mc_range TEXT,
                best_hour INTEGER,
                observation TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Management/settings tables
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS blocked_callers (
                sender_id INTEGER PRIMARY KEY,
                sender_name TEXT,
                reason TEXT,
                blocked_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS contract_blacklist (
                address TEXT PRIMARY KEY,
                chain TEXT,
                reason TEXT,
                added_at TEXT
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signal_notes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                note TEXT,
                created_at TEXT
            )
        """)

        # ── Performance indexes ──────────────────────────────────────────
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_token_address ON signals(token_address)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_original_timestamp ON signals(original_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_sender_id ON signals(sender_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_chain ON signals(chain)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_runner ON signals(runner_alerted, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status_timestamp ON signals(status, original_timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_token_type_status ON signals(token_type, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_checked ON signals(checked_1h, checked_6h, status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_sender_status ON signals(sender_id, status)")

        conn.commit()
    logger.info("Database initialized")


def was_token_forwarded_recently(token_address, within_seconds=120):
    """Fast check: was this token forwarded in the last N seconds?"""
    if not token_address:
        return False
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            threshold = (utcnow_naive() - timedelta(seconds=within_seconds)).isoformat()
            addr = (token_address or "").strip()
            if addr.startswith("0x") and len(addr) == 42:
                cursor.execute(
                    """SELECT 1 FROM signals WHERE token_type = 'contract' AND original_timestamp > ?
                       AND LOWER(TRIM(token_address)) = LOWER(?) LIMIT 1""",
                    (threshold, addr),
                )
            else:
                cursor.execute(
                    "SELECT 1 FROM signals WHERE token_type = 'contract' AND token_address = ? AND original_timestamp > ? LIMIT 1",
                    (addr, threshold),
                )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.debug(f"Error checking recent forward: {e}")
        return False


def mark_source_message_processed(chat_id, message_id):
    """Record that we processed this (chat_id, message_id).
    Returns True if inserted (first time), False if duplicate."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO processed_source_messages (source_chat_id, source_message_id, processed_at) VALUES (?, ?, ?)",
                (chat_id, message_id, utcnow_iso()),
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError:
        return False
    except Exception as e:
        logger.error(f"Error marking source message: {e}")
        return False


def is_source_message_processed(chat_id, message_id):
    """Check if we have already processed this (chat_id, message_id)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM processed_source_messages WHERE source_chat_id = ? AND source_message_id = ? LIMIT 1",
                (chat_id, message_id),
            )
            return cursor.fetchone() is not None
    except Exception as e:
        logger.error(f"Error checking source message: {e}")
        return False


def claim_signal_if_new(token_address, chain, original_message_id, source_group, sender_id, sender_name, all_addresses=None):
    """Claim-before-forward: returns signal_id if claimed, None if duplicate."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("BEGIN IMMEDIATE")
            threshold_time = (utcnow_naive() - timedelta(hours=24)).isoformat()
            to_check = list(all_addresses) if all_addresses else [(chain, token_address)]
            for ch, addr in to_check:
                a = (addr or "").strip()
                if a.startswith("0x") and len(a) == 42:
                    cursor.execute(
                        """SELECT id FROM signals WHERE token_type = 'contract' AND original_timestamp > ?
                           AND LOWER(TRIM(token_address)) = LOWER(?) LIMIT 1""",
                        (threshold_time, a),
                    )
                else:
                    cursor.execute(
                        "SELECT id FROM signals WHERE token_type = 'contract' AND token_address = ? AND original_timestamp > ? LIMIT 1",
                        (a, threshold_time),
                    )
                if cursor.fetchone():
                    conn.rollback()
                    return None
            store_addr = token_address.lower() if token_address and str(token_address).startswith("0x") and len(str(token_address)) == 42 else token_address
            cursor.execute(
                """
                INSERT INTO signals (
                    original_message_id, forwarded_message_id, token_address, token_type, chain, ticker,
                    original_timestamp, sender_id, sender_name, source_group, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (original_message_id, None, store_addr, "contract", chain, "",
                 utcnow_iso(), sender_id, sender_name, source_group, "pending"),
            )
            signal_id = cursor.lastrowid
            conn.commit()
            logger.info(f"Claimed signal {signal_id} for {token_address[:8]}...")
            return signal_id
    except Exception as e:
        logger.error(f"Error claiming signal: {e}")
        return None


def update_signal_after_forward(
    signal_id, forwarded_message_id, token_info, dexscreener_data,
    original_dexscreener_link, signal_link, destination_type=None,
):
    """Fill in claimed signal after successful forward."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            token_address = token_info.get("address") or token_info.get("ticker")
            chain = token_info.get("chain", "")
            data_key = f"{chain}:{token_address}"
            data = dexscreener_data.get(data_key, {})
            # Use DexScreener's chain if available (more accurate than text-based detection)
            enriched_chain = data.get("chain") or chain
            token_name = data.get("token_name") or None
            token_symbol = data.get("token_symbol") or None
            original_price = float(data.get("price")) if data.get("price") else None
            original_volume = float(data.get("volume_24h")) if data.get("volume_24h") else None
            original_liquidity = float(data.get("liquidity")) if data.get("liquidity") else None
            original_market_cap = float(data.get("fdv")) if data.get("fdv") else None
            original_dex_id = data.get("exchange") or None

            ts = utcnow_naive()
            hour_utc = ts.hour
            day_of_week = ts.weekday()
            if 0 <= hour_utc < 8:
                session = "asia"
            elif 8 <= hour_utc < 16:
                session = "eu"
            else:
                session = "us"

            cursor.execute(
                """
                UPDATE signals SET
                    forwarded_message_id = ?, chain = ?, token_name = ?, token_symbol = ?,
                    original_price = ?, original_volume = ?, original_liquidity = ?, original_market_cap = ?,
                    original_dexscreener_link = ?, signal_link = ?, status = 'active',
                    original_dex_id = ?, destination_type = ?, hour_utc = ?, day_of_week = ?, session = ?
                WHERE id = ?
                """,
                (forwarded_message_id, enriched_chain, token_name, token_symbol,
                 original_price, original_volume, original_liquidity, original_market_cap,
                 original_dexscreener_link, signal_link,
                 original_dex_id, destination_type, hour_utc, day_of_week, session,
                 signal_id),
            )
            conn.commit()
            logger.info(f"Updated signal {signal_id} after forward")
    except Exception as e:
        logger.error(f"Error updating signal after forward: {e}")


def update_signal_minimal_after_forward(
    signal_id, forwarded_message_id, token_address, chain,
    original_dexscreener_link, signal_link, destination_type=None,
):
    """Update claimed signal with minimal data (no DexScreener data)."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE signals SET
                    forwarded_message_id = ?, status = 'active',
                    original_dexscreener_link = ?, signal_link = ?,
                    destination_type = ?
                WHERE id = ?
                """,
                (forwarded_message_id, original_dexscreener_link or None,
                 signal_link or None, destination_type or None, signal_id),
            )
            conn.commit()
            logger.info(f"Updated signal {signal_id} (minimal)")
    except Exception as e:
        logger.error(f"Error updating signal minimal: {e}")


def delete_claim(signal_id):
    """Remove a claimed-but-not-forwarded signal."""
    try:
        with get_connection() as conn:
            conn.execute("DELETE FROM signals WHERE id = ?", (signal_id,))
            conn.commit()
            logger.info(f"Deleted claim {signal_id}")
    except Exception as e:
        logger.error(f"Error deleting claim: {e}")


def get_signals_to_check_1h():
    """Signals needing 1-hour check. One per token_address."""
    with get_connection() as conn:
        one_hour_ago = (utcnow_naive() - timedelta(hours=1)).isoformat()
        return conn.execute(
            """SELECT * FROM signals WHERE id IN (
                SELECT MIN(id) FROM signals
                WHERE status = 'active' AND checked_1h = 0 AND original_timestamp < ?
                GROUP BY token_address
            )""",
            (one_hour_ago,),
        ).fetchall()


def get_signals_to_check_6h():
    """Signals needing 6-hour check (winners from 1h). One per token_address."""
    with get_connection() as conn:
        six_hours_ago = (utcnow_naive() - timedelta(hours=6)).isoformat()
        return conn.execute(
            """SELECT * FROM signals WHERE id IN (
                SELECT MIN(id) FROM signals
                WHERE status = 'win' AND checked_1h = 1 AND checked_6h = 0 AND original_timestamp < ?
                GROUP BY token_address
            )""",
            (six_hours_ago,),
        ).fetchall()


def get_signals_for_runner_check(max_age_minutes=60, min_age_minutes=2):
    """Active signals in the early momentum window, not yet runner-alerted."""
    with get_connection() as conn:
        now = utcnow_naive()
        oldest = (now - timedelta(minutes=max_age_minutes)).isoformat()
        youngest = (now - timedelta(minutes=min_age_minutes)).isoformat()
        return conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active' AND token_type = 'contract'
            AND (runner_alerted = 0 OR runner_alerted IS NULL)
            AND original_timestamp > ? AND original_timestamp < ?
            ORDER BY original_timestamp DESC
            LIMIT 50
            """,
            (oldest, youngest),
        ).fetchall()


def get_runner_exit_candidates(max_age_hours=24):
    """Active signals that were runner-alerted, for exit signal monitoring."""
    with get_connection() as conn:
        now = utcnow_naive()
        oldest = (now - timedelta(hours=max_age_hours)).isoformat()
        return conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active' AND token_type = 'contract'
            AND runner_alerted = 1
            AND original_timestamp > ?
            ORDER BY runner_alerted_at DESC
            """,
            (oldest,),
        ).fetchall()


def get_all_active_signals():
    """All active signals for daily report."""
    with get_connection() as conn:
        return conn.execute("SELECT * FROM signals WHERE status IN ('active', 'win', 'loss') LIMIT 500").fetchall()


def update_signal_performance(signal_id, current_data, is_winner, time_label=None):
    """Update signal with current performance and optional 1h/6h snapshot."""
    try:
        with get_connection() as conn:
            cursor = conn.cursor()

            current_price = float(current_data.get("price", 0)) if current_data.get("price") else None
            current_volume = float(current_data.get("volume_24h", 0)) if current_data.get("volume_24h") else None
            current_liquidity = float(current_data.get("liquidity", 0)) if current_data.get("liquidity") else None
            current_market_cap = float(current_data.get("fdv", 0)) if current_data.get("fdv") else None

            row = cursor.execute(
                "SELECT original_price, max_price_seen, max_market_cap_seen FROM signals WHERE id = ?",
                (signal_id,),
            ).fetchone()
            original_price = row["original_price"] if row else None
            max_price_seen = row["max_price_seen"] if row else None
            max_mc_seen = row["max_market_cap_seen"] if row else None

            price_change_percent = None
            multiplier = None
            if original_price and current_price and original_price > 0:
                price_change_percent = ((current_price - original_price) / original_price) * 100
                multiplier = current_price / original_price

            new_max_price = max_price_seen
            new_max_mc = max_mc_seen
            now_iso = utcnow_iso()
            if current_price is not None and (max_price_seen is None or current_price > max_price_seen):
                new_max_price = current_price
            if current_market_cap is not None and (max_mc_seen is None or current_market_cap > max_mc_seen):
                new_max_mc = current_market_cap

            status = "win" if is_winner else "loss"

            cursor.execute(
                """
                UPDATE signals SET
                    current_price = ?, current_volume = ?, current_liquidity = ?,
                    current_market_cap = ?, price_change_percent = ?, multiplier = ?,
                    status = ?, last_check_timestamp = ?,
                    max_price_seen = ?, max_price_seen_at = ?, max_market_cap_seen = ?, max_market_cap_seen_at = ?
                WHERE id = ?
                """,
                (current_price, current_volume, current_liquidity, current_market_cap,
                 price_change_percent, multiplier, status, now_iso,
                 new_max_price, now_iso, new_max_mc, now_iso, signal_id),
            )

            if time_label == "1h":
                cursor.execute(
                    "UPDATE signals SET checked_1h_at = ?, price_1h = ?, market_cap_1h = ?, price_change_1h = ?, multiplier_1h = ? WHERE id = ?",
                    (now_iso, current_price, current_market_cap, price_change_percent, multiplier, signal_id),
                )
            elif time_label == "6h":
                cursor.execute(
                    "UPDATE signals SET checked_6h_at = ?, price_6h = ?, market_cap_6h = ?, price_change_6h = ?, multiplier_6h = ? WHERE id = ?",
                    (now_iso, current_price, current_market_cap, price_change_percent, multiplier, signal_id),
                )

            conn.commit()
    except Exception as e:
        logger.error(f"Error updating signal performance: {e}")


def mark_signal_checked_1h(signal_id):
    """Mark as checked (all duplicate rows with same token_address)."""
    with get_connection() as conn:
        row = conn.execute("SELECT token_address FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if row and row["token_address"]:
            conn.execute("UPDATE signals SET checked_1h = 1 WHERE token_address = ?", (row["token_address"],))
        else:
            conn.execute("UPDATE signals SET checked_1h = 1 WHERE id = ?", (signal_id,))
        conn.commit()


def mark_signal_checked_6h(signal_id):
    """Mark as checked (all duplicate rows with same token_address)."""
    with get_connection() as conn:
        row = conn.execute("SELECT token_address FROM signals WHERE id = ?", (signal_id,)).fetchone()
        if row and row["token_address"]:
            conn.execute("UPDATE signals SET checked_6h = 1 WHERE token_address = ?", (row["token_address"],))
        else:
            conn.execute("UPDATE signals SET checked_6h = 1 WHERE id = ?", (signal_id,))
        conn.commit()


def mark_runner_alerted(signal_id):
    """Mark signal as runner-alerted."""
    with get_connection() as conn:
        conn.execute(
            "UPDATE signals SET runner_alerted = 1, runner_alerted_at = ? WHERE id = ?",
            (utcnow_iso(), signal_id),
        )
        conn.commit()


def update_max_tracking(signal_id, current_price, current_market_cap):
    """Update max price/MC for runner watcher."""
    try:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT max_price_seen, max_market_cap_seen FROM signals WHERE id = ?",
                (signal_id,),
            ).fetchone()
            max_price = row["max_price_seen"] if row else None
            max_mc = row["max_market_cap_seen"] if row else None
            now_iso = utcnow_iso()
            new_max_price = max_price
            new_max_mc = max_mc
            if current_price is not None and (max_price is None or current_price > max_price):
                new_max_price = current_price
            if current_market_cap is not None and (max_mc is None or current_market_cap > max_mc):
                new_max_mc = current_market_cap
            conn.execute(
                "UPDATE signals SET max_price_seen = ?, max_price_seen_at = ?, max_market_cap_seen = ?, max_market_cap_seen_at = ? WHERE id = ?",
                (new_max_price, now_iso, new_max_mc, now_iso, signal_id),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error updating max tracking: {e}")


def delete_losing_signals():
    with get_connection() as conn:
        cursor = conn.execute('DELETE FROM signals WHERE status = "loss"')
        deleted_count = cursor.rowcount
        conn.commit()
        logger.info(f"Deleted {deleted_count} losing signals")
        return deleted_count


def enforce_capacity(max_count):
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]
        if total <= max_count:
            return 0
        to_remove = total - max_count
        ids = [row["id"] for row in conn.execute("SELECT id FROM signals ORDER BY id ASC LIMIT ?", (to_remove,)).fetchall()]
        if ids:
            placeholders = ",".join("?" * len(ids))
            conn.execute(f"DELETE FROM signals WHERE id IN ({placeholders})", ids)
            deleted = len(ids)
        else:
            deleted = 0
        conn.commit()
        logger.info(f"Capacity cleanup: removed {deleted} oldest signals (max {max_count})")
        return deleted


def get_winning_signals():
    with get_connection() as conn:
        return conn.execute('SELECT * FROM signals WHERE status = "win" ORDER BY created_at DESC').fetchall()


def delete_signal(signal_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM signals WHERE id = ?", (signal_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def get_signal_by_id(signal_id):
    with get_connection() as conn:
        return conn.execute("SELECT * FROM signals WHERE id = ?", (signal_id,)).fetchone()


def get_signals_count():
    with get_connection() as conn:
        return conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]


def is_duplicate_signal(contract_addresses, hours_window=24):
    """Check if any contract was forwarded in the last N hours."""
    if not contract_addresses:
        return False
    with get_connection() as conn:
        threshold = (utcnow_naive() - timedelta(hours=hours_window)).isoformat()
        for chain, address in contract_addresses:
            addr = (address or "").strip()
            if addr.startswith("0x") and len(addr) == 42:
                row = conn.execute(
                    """SELECT id FROM signals WHERE token_type = 'contract' AND original_timestamp > ?
                       AND LOWER(TRIM(token_address)) = LOWER(?) LIMIT 1""",
                    (threshold, addr),
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT id FROM signals WHERE token_type = 'contract' AND token_address = ? AND original_timestamp > ? LIMIT 1",
                    (addr, threshold),
                ).fetchone()
            if row:
                return True
    return False


def save_analytics_daily(report_date, total_signals, win_count, loss_count, active_count, runner_count, best_mc_range=None, best_hour=None, observation=None):
    """Insert or replace daily analytics."""
    try:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO analytics_daily
                (report_date, total_signals, win_count, loss_count, active_count, runner_count, best_mc_range, best_hour, observation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (report_date, total_signals, win_count, loss_count, active_count, runner_count, best_mc_range, best_hour, observation, utcnow_iso()),
            )
            conn.commit()
    except Exception as e:
        logger.error(f"Error saving analytics daily: {e}")
