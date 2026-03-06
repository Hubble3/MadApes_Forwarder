"""Runner alert endpoints."""
from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from db import get_connection

router = APIRouter()


@router.get("/")
async def list_runners(
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Get signals that triggered runner alerts."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM signals
               WHERE runner_alerted = 1
               ORDER BY runner_alerted_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return {
        "runners": [
            {key: row[key] for key in row.keys()}
            for row in rows
        ]
    }


@router.get("/stats")
async def runner_stats(api_key: str = Depends(verify_api_key)):
    """Get runner detection statistics."""
    with get_connection() as conn:
        total_runners = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE runner_alerted = 1"
        ).fetchone()["cnt"]
        total_signals = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE status IN ('active','win','loss')"
        ).fetchone()["cnt"]

        # Runner win rate
        runner_wins = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE runner_alerted = 1 AND status = 'win'"
        ).fetchone()["cnt"]
        runner_checked = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals WHERE runner_alerted = 1 AND status IN ('win','loss')"
        ).fetchone()["cnt"]

        # Average return for runners
        avg_row = conn.execute(
            "SELECT AVG(price_change_percent) as avg FROM signals WHERE runner_alerted = 1 AND price_change_percent IS NOT NULL"
        ).fetchone()

    return {
        "total_runners": total_runners,
        "total_signals": total_signals,
        "runner_rate": round((total_runners / total_signals * 100) if total_signals > 0 else 0, 1),
        "runner_win_rate": round((runner_wins / runner_checked * 100) if runner_checked > 0 else 0, 1),
        "runner_avg_return": round(avg_row["avg"] or 0, 2),
    }
