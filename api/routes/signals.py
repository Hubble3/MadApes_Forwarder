"""Signal endpoints."""
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
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
    d = {key: row[key] for key in row.keys()}
    # Add computed signal quality classification
    from db import classify_signal_quality
    d["signal_quality"] = classify_signal_quality(row)
    return d


def _mc_filter_clause():
    """Return SQL clause and params to filter signals by min market cap setting."""
    min_mc = get_min_market_cap()
    if min_mc > 0:
        return " AND (original_market_cap IS NULL OR original_market_cap >= ?)", [min_mc]
    return "", []


_SORT_COLUMNS = {
    "date": "original_timestamp",
    "pnl": "price_change_percent",
    "multiplier": "multiplier",
    "market_cap": "original_market_cap",
    "confidence": "confidence_score",
    "runner_potential": "runner_potential_score",
}


@router.get("/")
async def list_signals(
    status: Optional[str] = Query(None, description="Filter by status: active, win, loss"),
    chain: Optional[str] = Query(None),
    sender_id: Optional[int] = Query(None),
    tier: Optional[str] = Query(None, description="Filter by signal tier: gold, silver, bronze"),
    quality: Optional[str] = Query(None, description="Filter by signal quality: valuable, borderline, junk"),
    search: Optional[str] = Query(None, description="Search by token name, symbol, or address"),
    sort: Optional[str] = Query(None, description="Sort by: date, pnl, multiplier, market_cap, confidence, runner_potential"),
    order: Optional[str] = Query("desc", description="Sort order: asc or desc"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    api_key: str = Depends(verify_api_key),
):
    """List signals with optional filters and sorting."""
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
        if tier:
            query += " AND signal_tier = ?"
            params.append(tier.lower())
        if search:
            query += " AND (token_name LIKE ? OR token_symbol LIKE ? OR token_address LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])
        if quality:
            query += " AND signal_quality = ?"
            params.append(quality.lower())

        # Sorting
        sort_col = _SORT_COLUMNS.get(sort, "original_timestamp")
        sort_dir = "ASC" if order and order.lower() == "asc" else "DESC"
        query += f" ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?"
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
        tp1 = conn.execute(base + " AND tp1_hit=1", mc_params).fetchone()["cnt"]
        tp2 = conn.execute(base + " AND tp2_hit=1", mc_params).fetchone()["cnt"]
        tp3 = conn.execute(base + " AND tp3_hit=1", mc_params).fetchone()["cnt"]
        tp4 = conn.execute(base + " AND tp4_hit=1", mc_params).fetchone()["cnt"]
        quality_rows = conn.execute(
            "SELECT signal_quality, COUNT(*) as cnt FROM signals WHERE 1=1" + mc_clause + " AND signal_quality IS NOT NULL GROUP BY signal_quality",
            mc_params,
        ).fetchall()
    checked = wins + losses
    quality_dist = {r["signal_quality"]: r["cnt"] for r in quality_rows}
    return {
        "total": total,
        "active": active,
        "wins": wins,
        "losses": losses,
        "checked": checked,
        "win_rate": round((wins / checked * 100) if checked > 0 else 0, 1),
        "tp1_count": tp1,
        "tp2_count": tp2,
        "tp3_count": tp3,
        "tp4_count": tp4,
        "quality_distribution": quality_dist,
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

    # Auto-fill missing entry prices + update peak tracking
    if prices:
        try:
            from utils import utcnow_iso
            now_iso = utcnow_iso()
            with get_connection() as conn:
                # Auto-fill missing entry prices
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

                # Update peak price/MC when live data exceeds stored peaks
                peak_ids = list(int(k) for k in prices.keys())
                peak_rows = conn.execute(
                    "SELECT id, max_price_seen, max_market_cap_seen FROM signals WHERE id IN ({})".format(
                        ",".join("?" for _ in peak_ids)
                    ),
                    peak_ids,
                ).fetchall()

                updated = False
                for row in peak_rows:
                    sid = str(row["id"])
                    live = prices.get(sid)
                    if not live:
                        continue
                    live_price = live.get("price")
                    live_mc = live.get("market_cap")
                    stored_peak_price = row["max_price_seen"]
                    stored_peak_mc = row["max_market_cap_seen"]

                    new_peak_price = stored_peak_price
                    new_peak_mc = stored_peak_mc
                    need_update = False

                    if live_price is not None and (stored_peak_price is None or live_price > stored_peak_price):
                        new_peak_price = live_price
                        need_update = True
                    if live_mc is not None and (stored_peak_mc is None or live_mc > stored_peak_mc):
                        new_peak_mc = live_mc
                        need_update = True

                    if need_update:
                        conn.execute(
                            "UPDATE signals SET max_price_seen = ?, max_price_seen_at = ?, max_market_cap_seen = ?, max_market_cap_seen_at = ? WHERE id = ?",
                            (new_peak_price, now_iso, new_peak_mc, now_iso, int(sid)),
                        )
                        updated = True

                if missing or updated:
                    conn.commit()
        except Exception as e:
            logger.debug(f"Auto-fill/peak update failed: {e}")

    return {"prices": prices}


@router.get("/{signal_id}")
async def get_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Get a specific signal by ID."""
    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")
    return {"signal": _row_to_dict(row)}
