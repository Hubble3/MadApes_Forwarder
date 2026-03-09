"""Leaderboard service - caller rankings by time window."""
import logging
from datetime import timedelta
from typing import List

from db import get_connection
from madapes.formatting import safe_float
from utils import utcnow_naive

logger = logging.getLogger(__name__)


def get_caller_leaderboard(window_days: int = 0, limit: int = 20) -> List[dict]:
    """Get caller leaderboard, optionally filtered by time window.

    window_days=0 means all-time.
    Returns list of dicts with caller stats, sorted by P&L.
    """
    with get_connection() as conn:
        if window_days > 0:
            cutoff = (utcnow_naive() - timedelta(days=window_days)).isoformat()
            time_clause = "AND s.original_timestamp > ?"
            params = [cutoff]
        else:
            time_clause = ""
            params = []

        rows = conn.execute(
            f"""SELECT
                s.sender_id,
                s.sender_name,
                COUNT(*) as total_signals,
                SUM(CASE WHEN s.status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN s.status = 'loss' THEN 1 ELSE 0 END) as losses,
                SUM(CASE WHEN s.runner_alerted = 1 THEN 1 ELSE 0 END) as runners,
                AVG(CASE WHEN s.price_change_percent IS NOT NULL THEN s.price_change_percent END) as avg_return,
                MAX(s.price_change_percent) as best_return,
                MIN(CASE WHEN s.status = 'loss' THEN s.price_change_percent END) as worst_return
            FROM signals s
            WHERE s.sender_id IS NOT NULL
              AND s.status IN ('win', 'loss')
              {time_clause}
            GROUP BY s.sender_id
            HAVING COUNT(*) >= 2
            ORDER BY AVG(CASE WHEN s.price_change_percent IS NOT NULL THEN s.price_change_percent END) DESC
            LIMIT ?""",
            (*params, limit),
        ).fetchall()

    leaderboard = []
    for rank, r in enumerate(rows, 1):
        total_checked = (r["wins"] or 0) + (r["losses"] or 0)
        win_rate = (r["wins"] / total_checked * 100) if total_checked > 0 else 0
        leaderboard.append({
            "rank": rank,
            "sender_id": r["sender_id"],
            "sender_name": r["sender_name"] or "Unknown",
            "total_signals": r["total_signals"],
            "wins": r["wins"] or 0,
            "losses": r["losses"] or 0,
            "runners": r["runners"] or 0,
            "win_rate": round(win_rate, 1),
            "avg_return": round(r["avg_return"], 2) if r["avg_return"] is not None else None,
            "best_return": round(r["best_return"], 2) if r["best_return"] is not None else None,
            "worst_return": round(r["worst_return"], 2) if r["worst_return"] is not None else None,
        })
    return leaderboard


def format_leaderboard_message(leaderboard: List[dict], window_label: str = "All-Time") -> str:
    """Format leaderboard as an HTML message for Telegram."""
    if not leaderboard:
        return f"\U0001f3c6 <b>Caller Leaderboard ({window_label})</b>\n\nNo data yet."

    lines = [
        "\u2501" * 32,
        f"\U0001f3c6 <b>CALLER LEADERBOARD ({window_label})</b>",
        "",
    ]

    medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}

    for entry in leaderboard[:10]:
        rank = entry["rank"]
        medal = medals.get(rank, f"{rank}.")
        name = entry["sender_name"]
        wr = entry["win_rate"]
        avg = entry["avg_return"]
        total = entry["total_signals"]

        avg_emoji = "\U0001f7e2" if avg >= 0 else "\U0001f534"
        lines.append(
            f"{medal} <b>{name}</b> | {avg_emoji} {avg:+.1f}% avg | "
            f"WR: {wr:.0f}% | {total} signals"
        )

    lines.append("")
    lines.append("\u2501" * 32)
    return "\n".join(lines)


def get_performance_attribution() -> dict:
    """Get performance attribution by chain, MC range, time-of-day, and session."""
    with get_connection() as conn:
        # By chain
        chain_rows = conn.execute(
            """SELECT chain,
                      COUNT(*) as total,
                      SUM(CASE WHEN status='win' THEN 1 ELSE 0 END) as wins,
                      AVG(price_change_percent) as avg_return
               FROM signals WHERE status IN ('win','loss') AND chain IS NOT NULL
               GROUP BY chain ORDER BY AVG(price_change_percent) DESC"""
        ).fetchall()

        # By MC range (using destination_type as proxy)
        mc_rows = conn.execute(
            """SELECT destination_type,
                      COUNT(*) as total,
                      SUM(CASE WHEN status='win' THEN 1 ELSE 0 END) as wins,
                      AVG(price_change_percent) as avg_return
               FROM signals WHERE status IN ('win','loss') AND destination_type IS NOT NULL
               GROUP BY destination_type"""
        ).fetchall()

        # By session
        session_rows = conn.execute(
            """SELECT session,
                      COUNT(*) as total,
                      SUM(CASE WHEN status='win' THEN 1 ELSE 0 END) as wins,
                      AVG(price_change_percent) as avg_return
               FROM signals WHERE status IN ('win','loss') AND session IS NOT NULL
               GROUP BY session ORDER BY AVG(price_change_percent) DESC"""
        ).fetchall()

        # By hour
        hour_rows = conn.execute(
            """SELECT hour_utc,
                      COUNT(*) as total,
                      SUM(CASE WHEN status='win' THEN 1 ELSE 0 END) as wins,
                      AVG(price_change_percent) as avg_return
               FROM signals WHERE status IN ('win','loss') AND hour_utc IS NOT NULL
               GROUP BY hour_utc ORDER BY AVG(price_change_percent) DESC
               LIMIT 5"""
        ).fetchall()

    def _format_rows(rows):
        result = []
        for r in rows:
            total = r["total"]
            wins = r["wins"] or 0
            result.append({
                "total": total,
                "wins": wins,
                "win_rate": round((wins / total * 100) if total > 0 else 0, 1),
                "avg_return": round(r["avg_return"] or 0, 2),
            })
        return result

    return {
        "by_chain": {r["chain"]: _format_rows([r])[0] for r in chain_rows},
        "by_mc_range": {r["destination_type"]: _format_rows([r])[0] for r in mc_rows},
        "by_session": {r["session"]: _format_rows([r])[0] for r in session_rows},
        "best_hours": [{"hour_utc": r["hour_utc"], **_format_rows([r])[0]} for r in hour_rows],
    }


def format_attribution_message(attribution: dict) -> str:
    """Format performance attribution for display."""
    lines = [
        "\u2501" * 32,
        "\U0001f4ca <b>PERFORMANCE ATTRIBUTION</b>",
        "",
    ]

    # By chain
    by_chain = attribution.get("by_chain", {})
    if by_chain:
        lines.append("<b>By Chain:</b>")
        for chain, stats in by_chain.items():
            emoji = "\U0001f7e2" if stats["avg_return"] >= 0 else "\U0001f534"
            lines.append(
                f"  {(chain or '?').upper()}: {emoji} {stats['avg_return']:+.1f}% avg | "
                f"WR: {stats['win_rate']:.0f}% | {stats['total']} signals"
            )
        lines.append("")

    # By session
    by_session = attribution.get("by_session", {})
    if by_session:
        lines.append("<b>By Session:</b>")
        for session, stats in by_session.items():
            emoji = "\U0001f7e2" if stats["avg_return"] >= 0 else "\U0001f534"
            lines.append(
                f"  {(session or '?').upper()}: {emoji} {stats['avg_return']:+.1f}% avg | "
                f"WR: {stats['win_rate']:.0f}%"
            )
        lines.append("")

    # Best hours
    best_hours = attribution.get("best_hours", [])
    if best_hours:
        lines.append("<b>Best Hours (UTC):</b>")
        for h in best_hours[:3]:
            emoji = "\U0001f7e2" if h["avg_return"] >= 0 else "\U0001f534"
            lines.append(
                f"  {h['hour_utc']:02d}:00: {emoji} {h['avg_return']:+.1f}% avg | "
                f"WR: {h['win_rate']:.0f}%"
            )

    lines.append("\u2501" * 32)
    return "\n".join(lines)
