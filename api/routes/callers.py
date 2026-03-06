"""Caller endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from api.auth import verify_api_key
from madapes.services.caller_service import get_caller, get_all_callers

router = APIRouter()


def _caller_to_dict(caller):
    if caller is None:
        return None
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
        return {"error": "Caller not found"}, 404
    return {"caller": _caller_to_dict(caller)}
