"""Analytics endpoints."""
from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from db import get_connection
from madapes.services.leaderboard_service import get_performance_attribution

router = APIRouter()


@router.get("/attribution")
async def performance_attribution(api_key: str = Depends(verify_api_key)):
    """Get performance attribution (by chain, session, MC range, hour)."""
    return get_performance_attribution()


@router.get("/daily")
async def daily_analytics(
    limit: int = Query(30, ge=1, le=365),
    api_key: str = Depends(verify_api_key),
):
    """Get daily analytics history."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM analytics_daily ORDER BY report_date DESC LIMIT ?",
            (limit,),
        ).fetchall()
    days = []
    for row in rows:
        d = {key: row[key] for key in row.keys()}
        # Rename DB columns to frontend-expected names
        if "win_count" in d:
            d["wins"] = d.pop("win_count")
        if "loss_count" in d:
            d["losses"] = d.pop("loss_count")
        wins = d.get("wins", 0) or 0
        losses = d.get("losses", 0) or 0
        checked = wins + losses
        d["win_rate"] = round((wins / checked * 100) if checked > 0 else 0, 1)
        days.append(d)
    return {"days": days}


@router.get("/overview")
async def overview(api_key: str = Depends(verify_api_key)):
    """Dashboard overview: counts, win rate, recent activity."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]
        wins = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='win'").fetchone()["cnt"]
        losses = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='loss'").fetchone()["cnt"]
        active = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='active'").fetchone()["cnt"]
        runners = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE runner_alerted=1").fetchone()["cnt"]

        # Today's signals
        from utils import utcnow_naive
        from datetime import timedelta
        today_cutoff = (utcnow_naive() - timedelta(hours=24)).isoformat()
        today_count = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE original_timestamp > ?",
            (today_cutoff,),
        ).fetchone()["cnt"]

        # Chain distribution
        chain_rows = conn.execute(
            """SELECT chain, COUNT(*) as cnt FROM signals
               WHERE chain IS NOT NULL GROUP BY chain ORDER BY cnt DESC"""
        ).fetchall()

    checked = wins + losses
    return {
        "total_signals": total,
        "active": active,
        "wins": wins,
        "losses": losses,
        "runners": runners,
        "checked_signals": checked,
        "win_rate": round((wins / checked * 100) if checked > 0 else 0, 1),
        "today_signals": today_count,
        "chains": {r["chain"]: r["cnt"] for r in chain_rows},
    }
