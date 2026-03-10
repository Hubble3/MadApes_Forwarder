"""Caller endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from api.auth import verify_api_key
from madapes.services.caller_service import get_caller, get_all_callers

router = APIRouter()


def _caller_to_dict(caller):
    if caller is None:
        return None
    checked = (caller.win_count or 0) + (caller.loss_count or 0)
    return {
        "sender_id": caller.sender_id,
        "sender_name": caller.sender_name,
        "total_signals": caller.total_signals,
        "win_count": caller.win_count,
        "loss_count": caller.loss_count,
        "runner_count": caller.runner_count,
        "avg_return": caller.avg_return,
        "best_return": caller.best_return,
        "worst_return": caller.worst_return,
        "composite_score": caller.composite_score,
        "last_signal_at": caller.last_signal_at,
        "win_rate": round((caller.win_count / checked * 100) if checked > 0 else 0, 1),
        "big_win_count": caller.big_win_count,
        "runner_rate": caller.runner_rate,
        "big_win_rate": caller.big_win_rate,
        "best_chain": caller.best_chain,
    }


@router.get("/")
async def list_callers(
    min_signals: int = Query(1, ge=1),
    api_key: str = Depends(verify_api_key),
):
    """List all callers sorted by composite score."""
    callers = get_all_callers(min_signals=min_signals)
    return {"callers": [_caller_to_dict(c) for c in callers]}


@router.get("/{sender_id}")
async def get_caller_detail(sender_id: int, api_key: str = Depends(verify_api_key)):
    """Get caller details by sender ID."""
    caller = get_caller(sender_id)
    if not caller:
        raise HTTPException(status_code=404, detail="Caller not found")
    return {"caller": _caller_to_dict(caller)}


@router.get("/{sender_id}/signals")
async def get_caller_signals(
    sender_id: int,
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Get recent signals from a specific caller."""
    from db import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE sender_id = ? ORDER BY original_timestamp DESC LIMIT ?",
            (sender_id, limit),
        ).fetchall()
    return {
        "signals": [{key: row[key] for key in row.keys()} for row in rows],
        "total": len(rows),
    }
