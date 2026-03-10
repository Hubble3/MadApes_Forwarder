"""Caller scoring service - tracks caller performance and computes composite scores."""
import logging
import math
from typing import Optional, List

from db import get_connection
from madapes.models import Caller
from utils import utcnow_iso, utcnow_naive

logger = logging.getLogger(__name__)

# Score weights
W_WIN_RATE = 0.40
W_AVG_RETURN = 0.30
W_CONSISTENCY = 0.20
W_RECENCY = 0.10

# Recency decay: signals older than this many days get reduced weight
RECENCY_HALF_LIFE_DAYS = 14


def _ensure_callers_table():
    """Create callers table if it doesn't exist, and run migrations."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS callers (
                sender_id INTEGER PRIMARY KEY,
                sender_name TEXT,
                total_signals INTEGER DEFAULT 0,
                win_count INTEGER DEFAULT 0,
                loss_count INTEGER DEFAULT 0,
                runner_count INTEGER DEFAULT 0,
                avg_return REAL DEFAULT 0.0,
                best_return REAL DEFAULT 0.0,
                worst_return REAL DEFAULT 0.0,
                composite_score REAL DEFAULT 0.0,
                last_signal_at TEXT,
                updated_at TEXT
            )
        """)
        # Enhanced caller metrics migration
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(callers)").fetchall()}
        for col, col_type in [
            ("big_win_count", "INTEGER DEFAULT 0"),
            ("runner_rate", "REAL DEFAULT 0.0"),
            ("big_win_rate", "REAL DEFAULT 0.0"),
            ("best_chain", "TEXT"),
            ("avg_time_to_peak_min", "REAL"),
        ]:
            if col not in existing:
                conn.execute(f"ALTER TABLE callers ADD COLUMN {col} {col_type}")
        conn.commit()


def get_caller(sender_id: int) -> Optional[Caller]:
    """Get caller stats by sender ID."""
    _ensure_callers_table()
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM callers WHERE sender_id = ?", (sender_id,)
        ).fetchone()
        if row is None:
            return None
        cols = row.keys()
        return Caller(
            sender_id=row["sender_id"],
            sender_name=row["sender_name"] or "",
            total_signals=row["total_signals"],
            win_count=row["win_count"],
            loss_count=row["loss_count"],
            runner_count=row["runner_count"],
            avg_return=row["avg_return"],
            best_return=row["best_return"],
            worst_return=row["worst_return"],
            composite_score=row["composite_score"],
            last_signal_at=row["last_signal_at"],
            big_win_count=row["big_win_count"] if "big_win_count" in cols else 0,
            runner_rate=row["runner_rate"] if "runner_rate" in cols else 0.0,
            big_win_rate=row["big_win_rate"] if "big_win_rate" in cols else 0.0,
            best_chain=row["best_chain"] if "best_chain" in cols else None,
        )


def get_all_callers(min_signals: int = 1) -> List[Caller]:
    """Get all callers with at least min_signals signals."""
    _ensure_callers_table()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM callers WHERE total_signals >= ? ORDER BY composite_score DESC",
            (min_signals,),
        ).fetchall()
        cols = rows[0].keys() if rows else []
        return [
            Caller(
                sender_id=r["sender_id"],
                sender_name=r["sender_name"] or "",
                total_signals=r["total_signals"],
                win_count=r["win_count"],
                loss_count=r["loss_count"],
                runner_count=r["runner_count"],
                avg_return=r["avg_return"],
                best_return=r["best_return"],
                worst_return=r["worst_return"],
                composite_score=r["composite_score"],
                last_signal_at=r["last_signal_at"],
                big_win_count=r["big_win_count"] if "big_win_count" in cols else 0,
                runner_rate=r["runner_rate"] if "runner_rate" in cols else 0.0,
                big_win_rate=r["big_win_rate"] if "big_win_rate" in cols else 0.0,
                best_chain=r["best_chain"] if "best_chain" in cols else None,
            )
            for r in rows
        ]


def _compute_composite_score(
    win_rate: float,
    avg_return: float,
    consistency: float,
    recency_factor: float,
) -> float:
    """Compute composite score 0-100 from components.

    win_rate: 0-1 fraction
    avg_return: percentage (can be negative)
    consistency: 0-1 (lower std dev = higher consistency)
    recency_factor: 0-1 (1.0 = very recent, decays)
    """
    # Win rate component (0-40 pts)
    win_pts = min(win_rate * 100, 100) * W_WIN_RATE

    # Avg return component (0-30 pts), capped at 500% for scoring
    return_normalized = max(0, min(avg_return, 500)) / 500
    return_pts = return_normalized * 100 * W_AVG_RETURN

    # Consistency component (0-20 pts)
    consistency_pts = consistency * 100 * W_CONSISTENCY

    # Recency component (0-10 pts)
    recency_pts = recency_factor * 100 * W_RECENCY

    return min(round(win_pts + return_pts + consistency_pts + recency_pts, 1), 100)


def update_caller_stats(sender_id: int, sender_name: str = ""):
    """Recompute caller stats from signal history."""
    _ensure_callers_table()
    with get_connection() as conn:
        # Get all checked signals for this sender
        rows = conn.execute(
            """SELECT price_change_percent, status, runner_alerted, original_timestamp
               FROM signals
               WHERE sender_id = ? AND status IN ('win', 'loss')
               ORDER BY original_timestamp DESC""",
            (sender_id,),
        ).fetchall()

        if not rows:
            # Sender has signals but none checked yet - store minimal record
            existing = conn.execute(
                "SELECT COUNT(*) as cnt FROM signals WHERE sender_id = ?", (sender_id,)
            ).fetchone()
            total = existing["cnt"] if existing else 0
            last_row = conn.execute(
                "SELECT original_timestamp FROM signals WHERE sender_id = ? ORDER BY original_timestamp DESC LIMIT 1",
                (sender_id,),
            ).fetchone()
            conn.execute(
                """INSERT OR REPLACE INTO callers
                   (sender_id, sender_name, total_signals, win_count, loss_count, runner_count,
                    avg_return, best_return, worst_return, composite_score, last_signal_at, updated_at)
                   VALUES (?, ?, ?, 0, 0, 0, 0.0, 0.0, 0.0, 0.0, ?, ?)""",
                (sender_id, sender_name, total, last_row["original_timestamp"] if last_row else None, utcnow_iso()),
            )
            conn.commit()
            return

        returns = []
        win_count = 0
        loss_count = 0
        runner_count = 0

        now = utcnow_naive()
        weighted_returns = []

        for r in rows:
            pct = r["price_change_percent"]
            if pct is not None:
                returns.append(pct)

                # Recency-weighted return
                try:
                    from datetime import datetime
                    ts = datetime.fromisoformat(r["original_timestamp"])
                    days_ago = (now - ts).total_seconds() / 86400
                    weight = math.exp(-0.693 * days_ago / RECENCY_HALF_LIFE_DAYS)  # half-life decay
                except Exception:
                    weight = 0.5
                weighted_returns.append((pct, weight))

            if r["status"] == "win":
                win_count += 1
            elif r["status"] == "loss":
                loss_count += 1
            if r["runner_alerted"]:
                runner_count += 1

        total = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE sender_id = ?", (sender_id,)
        ).fetchone()["cnt"]

        checked_total = win_count + loss_count
        win_rate = win_count / checked_total if checked_total > 0 else 0

        avg_return = sum(returns) / len(returns) if returns else 0
        best_return = max(returns) if returns else 0
        worst_return = min(returns) if returns else 0

        # Consistency: 1 - normalized_std (lower variance = higher consistency)
        if len(returns) >= 2:
            mean = avg_return
            variance = sum((r - mean) ** 2 for r in returns) / len(returns)
            std = math.sqrt(variance)
            # Normalize: std of 100% = 0 consistency, std of 0% = 1.0 consistency
            consistency = max(0, 1 - (std / 100))
        else:
            consistency = 0.5  # Unknown consistency

        # Recency: weighted average of recency weights
        if weighted_returns:
            total_weight = sum(w for _, w in weighted_returns)
            recency_factor = total_weight / len(weighted_returns) if weighted_returns else 0.5
        else:
            recency_factor = 0.5

        score = _compute_composite_score(win_rate, avg_return, consistency, recency_factor)

        last_signal_at = rows[0]["original_timestamp"] if rows else None

        # Enhanced metrics: big wins (multiplier >= 5x), runner rate, best chain
        big_win_count = 0
        chain_runners = {}
        try:
            big_row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM signals WHERE sender_id = ? AND runner_alerted = 1 AND multiplier >= 5",
                (sender_id,),
            ).fetchone()
            big_win_count = big_row["cnt"] if big_row else 0

            chain_rows = conn.execute(
                "SELECT chain, COUNT(*) AS cnt FROM signals WHERE sender_id = ? AND status = 'win' GROUP BY chain ORDER BY cnt DESC",
                (sender_id,),
            ).fetchall()
            chain_runners = {r["chain"]: r["cnt"] for r in chain_rows} if chain_rows else {}
        except Exception:
            pass

        runner_rate_val = (runner_count / checked_total * 100) if checked_total > 0 else 0.0
        big_win_rate_val = (big_win_count / checked_total * 100) if checked_total > 0 else 0.0
        best_chain = max(chain_runners, key=chain_runners.get) if chain_runners else None

        conn.execute(
            """INSERT OR REPLACE INTO callers
               (sender_id, sender_name, total_signals, win_count, loss_count, runner_count,
                avg_return, best_return, worst_return, composite_score, last_signal_at, updated_at,
                big_win_count, runner_rate, big_win_rate, best_chain)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (sender_id, sender_name or "", total, win_count, loss_count, runner_count,
             round(avg_return, 2), round(best_return, 2), round(worst_return, 2),
             score, last_signal_at, utcnow_iso(),
             big_win_count, round(runner_rate_val, 2), round(big_win_rate_val, 2), best_chain),
        )
        conn.commit()
        logger.debug(f"Caller {sender_id} updated: score={score}, win_rate={win_rate:.0%}, runner_rate={runner_rate_val:.1f}%, avg_return={avg_return:.1f}%")


def get_caller_badge(sender_id: int) -> str:
    """Get a display badge for a caller based on their score.
    Returns HTML string like '[S+]' or '[A]' or '' if no data.
    """
    caller = get_caller(sender_id)
    if caller is None or caller.total_signals < 3:
        return ""

    score = caller.composite_score
    if score >= 90:
        return "<b>[S+]</b>"
    elif score >= 75:
        return "<b>[S]</b>"
    elif score >= 60:
        return "<b>[A]</b>"
    elif score >= 45:
        return "<b>[B]</b>"
    elif score >= 30:
        return "<b>[C]</b>"
    else:
        return "<b>[D]</b>"


def get_caller_score(sender_id: int) -> float:
    """Get the composite score for a caller (0-100). Returns 0 if unknown."""
    caller = get_caller(sender_id)
    return caller.composite_score if caller else 0.0
