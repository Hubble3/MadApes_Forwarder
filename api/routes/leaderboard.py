"""Leaderboard endpoints."""
from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from madapes.services.leaderboard_service import get_caller_leaderboard

router = APIRouter()


@router.get("/")
async def leaderboard(
    window: str = Query("all", description="Time window: 24h, 7d, 30d, all"),
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Get caller leaderboard."""
    window_days = {"24h": 1, "7d": 7, "30d": 30, "all": 0}.get(window, 0)
    entries = get_caller_leaderboard(window_days=window_days, limit=limit)
    return {"window": window, "leaderboard": entries}
