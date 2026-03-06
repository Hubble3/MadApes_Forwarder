"""Portfolio endpoints."""
from fastapi import APIRouter, Depends, Query

from api.auth import verify_api_key
from madapes.services.portfolio_service import (
    get_portfolio_summary,
    get_open_positions,
    get_closed_positions,
    get_portfolio_by_sender,
    get_portfolio_by_chain,
)

router = APIRouter()


def _row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


@router.get("/summary")
async def portfolio_summary(api_key: str = Depends(verify_api_key)):
    """Get aggregate portfolio metrics."""
    return get_portfolio_summary()


@router.get("/open")
async def open_positions(api_key: str = Depends(verify_api_key)):
    """Get all open positions."""
    rows = get_open_positions()
    return {"positions": [_row_to_dict(r) for r in rows]}


@router.get("/closed")
async def closed_positions(
    limit: int = Query(50, ge=1, le=200),
    api_key: str = Depends(verify_api_key),
):
    """Get recently closed positions."""
    rows = get_closed_positions(limit=limit)
    return {"positions": [_row_to_dict(r) for r in rows]}


@router.get("/by-chain")
async def portfolio_by_chain(api_key: str = Depends(verify_api_key)):
    """Get portfolio breakdown by chain."""
    return get_portfolio_by_chain()


@router.get("/by-sender/{sender_id}")
async def portfolio_by_sender(sender_id: int, api_key: str = Depends(verify_api_key)):
    """Get portfolio for a specific caller."""
    return get_portfolio_by_sender(sender_id)
