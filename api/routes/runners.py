"""Runner alert endpoints."""
from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from db import get_connection
from madapes.runtime_settings import get_min_market_cap

router = APIRouter()


def _mc_filter_clause():
    min_mc = get_min_market_cap()
    if min_mc > 0:
        return " AND (original_market_cap IS NULL OR original_market_cap >= ?)", [min_mc]
    return "", []


@router.get("/")
async def list_runners(
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Get signals that triggered runner alerts."""
    mc_clause, mc_params = _mc_filter_clause()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE runner_alerted = 1" + mc_clause + " ORDER BY runner_alerted_at DESC LIMIT ?",
            mc_params + [limit],
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
    mc_clause, mc_params = _mc_filter_clause()
    base = " WHERE 1=1" + mc_clause

    with get_connection() as conn:
        total_runners = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals" + base + " AND runner_alerted = 1",
            mc_params,
        ).fetchone()["cnt"]
        total_signals = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals" + base + " AND status IN ('active','win','loss')",
            mc_params,
        ).fetchone()["cnt"]

        runner_wins = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals" + base + " AND runner_alerted = 1 AND status = 'win'",
            mc_params,
        ).fetchone()["cnt"]
        runner_checked = conn.execute(
            "SELECT COUNT(*) as cnt FROM signals" + base + " AND runner_alerted = 1 AND status IN ('win','loss')",
            mc_params,
        ).fetchone()["cnt"]

        avg_row = conn.execute(
            "SELECT AVG(price_change_percent) as avg FROM signals" + base + " AND runner_alerted = 1 AND price_change_percent IS NOT NULL",
            mc_params,
        ).fetchone()

    return {
        "total_runners": total_runners,
        "total_signals": total_signals,
        "runner_rate": round((total_runners / total_signals * 100) if total_signals > 0 else 0, 1),
        "runner_win_rate": round((runner_wins / runner_checked * 100) if runner_checked > 0 else 0, 1),
        "runner_avg_return": round(avg_row["avg"] or 0, 2),
    }
