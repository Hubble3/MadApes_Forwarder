"""Signal endpoints."""
import asyncio
import logging
from fastapi import APIRouter, Depends, Query
from typing import Optional

from api.auth import verify_api_key
from db import get_connection, get_signal_by_id
from dexscreener import fetch_token_data
from madapes.runtime_settings import get_min_market_cap

logger = logging.getLogger(__name__)

router = APIRouter()


def _row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def _mc_filter_clause():
    """Return SQL clause and params to filter signals by min market cap setting."""
    min_mc = get_min_market_cap()
    if min_mc > 0:
        return " AND (original_market_cap IS NULL OR original_market_cap >= ?)", [min_mc]
    return "", []


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
    mc_clause, mc_params = _mc_filter_clause()

    with get_connection() as conn:
        query = "SELECT * FROM signals WHERE 1=1" + mc_clause
        params = list(mc_params)
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
    mc_clause, mc_params = _mc_filter_clause()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM signals WHERE 1=1" + mc_clause + " ORDER BY original_timestamp DESC LIMIT ?",
            mc_params + [limit],
        ).fetchall()
    return {"signals": [_row_to_dict(r) for r in rows]}


@router.get("/stats")
async def signal_stats(api_key: str = Depends(verify_api_key)):
    """Get signal count statistics."""
    mc_clause, mc_params = _mc_filter_clause()
    base = "SELECT COUNT(*) as cnt FROM signals WHERE 1=1" + mc_clause
    with get_connection() as conn:
        total = conn.execute(base, mc_params).fetchone()["cnt"]
        active = conn.execute(base + " AND status='active'", mc_params).fetchone()["cnt"]
        wins = conn.execute(base + " AND status='win'", mc_params).fetchone()["cnt"]
        losses = conn.execute(base + " AND status='loss'", mc_params).fetchone()["cnt"]
    checked = wins + losses
    return {
        "total": total,
        "active": active,
        "wins": wins,
        "losses": losses,
        "checked": checked,
        "win_rate": round((wins / checked * 100) if checked > 0 else 0, 1),
    }


@router.get("/live-prices")
async def live_prices(api_key: str = Depends(verify_api_key)):
    """Fetch live prices from DexScreener for all active signals."""
    mc_clause, mc_params = _mc_filter_clause()
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, token_address, chain FROM signals WHERE 1=1" + mc_clause + " ORDER BY original_timestamp DESC LIMIT 50",
            mc_params,
        ).fetchall()

    if not rows:
        return {"prices": {}}

    # Deduplicate by token_address
    unique_tokens = {}
    signal_to_token = {}
    for row in rows:
        addr = row["token_address"]
        if addr not in unique_tokens:
            unique_tokens[addr] = row["chain"]
        signal_to_token[row["id"]] = addr

    # Fetch concurrently (max 15)
    semaphore = asyncio.Semaphore(15)

    async def fetch_one(address: str, chain: str):
        async with semaphore:
            try:
                data = await fetch_token_data(chain, address)
                if data:
                    return address, {
                        "price": float(data["price"]) if data.get("price") else None,
                        "market_cap": float(data["fdv"]) if data.get("fdv") else None,
                        "price_change_5m": float(data["price_change_5m"]) if data.get("price_change_5m") else None,
                        "price_change_1h": float(data["price_change_1h"]) if data.get("price_change_1h") else None,
                        "price_change_24h": float(data["price_change_24h"]) if data.get("price_change_24h") else None,
                        "volume_24h": float(data["volume_24h"]) if data.get("volume_24h") else None,
                        "liquidity": float(data["liquidity"]) if data.get("liquidity") else None,
                    }
            except Exception as e:
                logger.debug(f"Live price fetch failed for {address[:8]}...: {e}")
            return address, None

    tasks = [fetch_one(addr, chain) for addr, chain in unique_tokens.items()]
    results = await asyncio.gather(*tasks)
    token_prices = {addr: data for addr, data in results if data is not None}

    # Map signal IDs to their live price data
    prices = {}
    for signal_id, addr in signal_to_token.items():
        if addr in token_prices:
            prices[str(signal_id)] = token_prices[addr]

    # Auto-fill missing entry prices
    if prices:
        try:
            with get_connection() as conn:
                missing = conn.execute(
                    "SELECT id, token_address FROM signals WHERE original_price IS NULL AND id IN ({})".format(
                        ",".join("?" for _ in prices)
                    ),
                    list(int(k) for k in prices.keys()),
                ).fetchall()
                for row in missing:
                    sid = str(row["id"])
                    live = prices.get(sid)
                    if live and live.get("price"):
                        conn.execute(
                            """UPDATE signals SET
                                original_price = ?, original_market_cap = ?,
                                original_liquidity = ?, original_volume = ?
                            WHERE id = ? AND original_price IS NULL""",
                            (live["price"], live["market_cap"], live["liquidity"], live["volume_24h"], int(sid)),
                        )
                        logger.info(f"Auto-filled entry price for signal {sid}: ${live['price']}")
                if missing:
                    conn.commit()
        except Exception as e:
            logger.debug(f"Auto-fill entry prices failed: {e}")

    return {"prices": prices}


@router.get("/{signal_id}")
async def get_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Get a specific signal by ID."""
    row = get_signal_by_id(signal_id)
    if not row:
        return {"error": "Signal not found"}
    return {"signal": _row_to_dict(row)}
