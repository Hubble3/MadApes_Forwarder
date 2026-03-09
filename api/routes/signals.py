"""Signal endpoints."""
from fastapi import APIRouter, Depends, Query
from typing import Optional

from api.auth import verify_api_key
from db import get_connection, get_signal_by_id

router = APIRouter()


def _row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


@router.get("/")
async def list_signals(
    status: Optional[str] = Query(None, description="Filter by status: active, win, loss"),
    chain: Optional[str] = Query(None),
    sender_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Search by token name, symbol, or address"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key),
):
    """List signals with optional filters."""
    with get_connection() as conn:
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if chain:
            query += " AND chain = ?"
            params.append(chain.lower())
        if sender_id:
            query += " AND sender_id = ?"
            params.append(sender_id)
        if search:
            query += " AND (token_name LIKE ? OR token_symbol LIKE ? OR token_address LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
        query += " ORDER BY original_timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        rows = conn.execute(query, params).fetchall()
        total = conn.execute(
            query.replace("SELECT *", "SELECT COUNT(*) as cnt").split("ORDER BY")[0],
            params[:-2],
        ).fetchone()["cnt"]

    return {
        "signals": [_row_to_dict(r) for r in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/recent")
async def recent_signals(
    limit: int = Query(20, ge=1, le=100),
    api_key: str = Depends(verify_api_key),
):
    """Get most recent signals."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals ORDER BY original_timestamp DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return {"signals": [_row_to_dict(r) for r in rows]}


@router.get("/stats")
async def signal_stats(api_key: str = Depends(verify_api_key)):
    """Get signal count statistics."""
    with get_connection() as conn:
        total = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]
        active = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='active'").fetchone()["cnt"]
        wins = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='win'").fetchone()["cnt"]
        losses = conn.execute("SELECT COUNT(*) as cnt FROM signals WHERE status='loss'").fetchone()["cnt"]
    return {
        "total": total,
        "active": active,
        "wins": wins,
        "losses": losses,
        "win_rate": round((wins / (wins + losses) * 100) if (wins + losses) > 0 else 0, 1),
    }


@router.get("/{signal_id}")
async def get_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Get a specific signal by ID."""
    row = get_signal_by_id(signal_id)
    if not row:
        return {"error": "Signal not found"}
    return {"signal": _row_to_dict(row)}
