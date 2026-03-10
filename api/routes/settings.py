"""Management/settings endpoints for MadApes Forwarder."""
import json
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.auth import verify_api_key
from db import get_connection, get_signal_by_id, DB_FILE
from utils import utcnow_iso
import config

router = APIRouter()


def _row_to_dict(row):
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


# ── Pydantic models ──────────────────────────────────────────────────

class SettingsUpdate(BaseModel):
    min_market_cap: Optional[float] = None
    mc_threshold: Optional[float] = None
    forward_delay: Optional[float] = None
    max_signals: Optional[int] = None
    display_timezone: Optional[str] = None
    runner_velocity_min: Optional[float] = None
    runner_vol_accel_min: Optional[float] = None
    runner_poll_interval: Optional[int] = None


# ── Helper: read settings with runtime overrides ─────────────────────

SETTINGS_KEYS = {
    "min_market_cap": lambda: str(config.MIN_MARKET_CAP),
    "mc_threshold": lambda: str(config.MC_THRESHOLD),
    "forward_delay": lambda: str(config.FORWARD_DELAY),
    "max_signals": lambda: str(config.MAX_SIGNALS),
    "display_timezone": lambda: config.DISPLAY_TIMEZONE,
    "runner_velocity_min": lambda: str(config.RUNNER_VELOCITY_MIN),
    "runner_vol_accel_min": lambda: str(config.RUNNER_VOL_ACCEL_MIN),
    "runner_poll_interval": lambda: str(config.RUNNER_POLL_INTERVAL),
    "source_groups": lambda: json.dumps(config.SOURCE_GROUPS),
    "report_destination": lambda: config.REPORT_DESTINATION or "",
}


def _get_all_settings() -> dict:
    """Return all settings, with runtime overrides from bot_settings table."""
    settings = {k: fn() for k, fn in SETTINGS_KEYS.items()}

    # Apply runtime overrides from DB
    try:
        with get_connection() as conn:
            rows = conn.execute("SELECT key, value FROM bot_settings").fetchall()
            for row in rows:
                settings[row["key"]] = row["value"]
    except Exception:
        pass

    # Parse types for JSON response
    result = {}
    for k, v in settings.items():
        if k in ("min_market_cap", "mc_threshold", "forward_delay", "runner_velocity_min", "runner_vol_accel_min"):
            try:
                result[k] = float(v)
            except (ValueError, TypeError):
                result[k] = v
        elif k in ("max_signals", "runner_poll_interval"):
            try:
                result[k] = int(v)
            except (ValueError, TypeError):
                result[k] = v
        elif k == "source_groups":
            try:
                result[k] = json.loads(v) if isinstance(v, str) else v
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        else:
            result[k] = v

    return result


# ── GET /api/settings/ ───────────────────────────────────────────────

@router.get("/")
async def get_settings(api_key: str = Depends(verify_api_key)):
    """Return all current bot settings."""
    return {"settings": _get_all_settings()}


# ── POST /api/settings/ ─────────────────────────────────────────────

@router.post("/")
async def update_settings(body: SettingsUpdate, api_key: str = Depends(verify_api_key)):
    """Update settings via runtime overrides stored in SQLite."""
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No settings provided")

    now = utcnow_iso()
    with get_connection() as conn:
        for key, value in updates.items():
            serialized = json.dumps(value) if isinstance(value, list) else str(value)
            conn.execute(
                """INSERT INTO bot_settings (key, value, updated_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
                (key, serialized, now),
            )
        conn.commit()

    return {"settings": _get_all_settings(), "updated_keys": list(updates.keys())}


# ── GET /api/settings/health ─────────────────────────────────────────

@router.get("/health")
async def system_health(api_key: str = Depends(verify_api_key)):
    """System health check with DB stats, Redis status, and uptime estimate."""
    db_stats = {}
    with get_connection() as conn:
        db_stats["total_signals"] = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]
        db_stats["total_callers"] = conn.execute(
            "SELECT COUNT(DISTINCT sender_id) as cnt FROM signals WHERE sender_id IS NOT NULL"
        ).fetchone()["cnt"]

        try:
            db_stats["portfolio_entries"] = conn.execute(
                "SELECT COUNT(*) as cnt FROM portfolio_entries"
            ).fetchone()["cnt"]
        except Exception:
            db_stats["portfolio_entries"] = 0

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        ).isoformat()
        first_today = conn.execute(
            "SELECT MIN(original_timestamp) as ts FROM signals WHERE original_timestamp >= ?",
            (today_start,),
        ).fetchone()

    try:
        db_stats["db_file_size_mb"] = round(os.path.getsize(DB_FILE) / (1024 * 1024), 2)
    except OSError:
        db_stats["db_file_size_mb"] = None

    uptime_seconds = None
    if first_today and first_today["ts"]:
        first_ts = datetime.fromisoformat(first_today["ts"])
        uptime_seconds = int((datetime.now(timezone.utc).replace(tzinfo=None) - first_ts).total_seconds())

    redis_status = "not_configured"
    if config.REDIS_URL:
        try:
            import redis.asyncio as aioredis
            r = aioredis.from_url(config.REDIS_URL)
            await r.ping()
            redis_status = "connected"
            await r.aclose()
        except Exception:
            redis_status = "error"

    return {
        "db": db_stats,
        "redis_status": redis_status,
        "uptime_seconds": uptime_seconds,
    }


# ── Signal operations ────────────────────────────────────────────────

@router.delete("/signals/{signal_id}")
async def delete_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Delete a signal from the database."""
    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    with get_connection() as conn:
        conn.execute("DELETE FROM signals WHERE id = ?", (signal_id,))
        conn.commit()
    return {"status": "deleted", "signal_id": signal_id}


@router.post("/signals/{signal_id}/recheck")
async def recheck_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Trigger a DexScreener refresh for a signal."""
    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    token_address = row["token_address"]
    chain = row["chain"]
    if not token_address:
        raise HTTPException(status_code=400, detail="Signal has no token address")

    try:
        from madapes.services.enrichment_service import enrich_token
        data = await enrich_token(chain or "solana", token_address)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"DexScreener fetch failed: {e}")

    if not data:
        return {"status": "no_data", "signal_id": signal_id}

    current_price = float(data.get("price")) if data.get("price") else None
    current_volume = float(data.get("volume_24h")) if data.get("volume_24h") else None
    current_liquidity = float(data.get("liquidity")) if data.get("liquidity") else None
    current_market_cap = float(data.get("fdv")) if data.get("fdv") else None

    original_price = row["original_price"]
    price_change = None
    multiplier = None
    if original_price and current_price and original_price > 0:
        price_change = ((current_price - original_price) / original_price) * 100
        multiplier = current_price / original_price

    now = utcnow_iso()
    with get_connection() as conn:
        conn.execute(
            """UPDATE signals SET
                current_price = ?, current_volume = ?, current_liquidity = ?,
                current_market_cap = ?, price_change_percent = ?, multiplier = ?,
                last_check_timestamp = ?
               WHERE id = ?""",
            (current_price, current_volume, current_liquidity, current_market_cap,
             price_change, multiplier, now, signal_id),
        )
        conn.commit()

    return {
        "status": "rechecked",
        "signal_id": signal_id,
        "current_price": current_price,
        "current_market_cap": current_market_cap,
        "price_change_percent": price_change,
        "multiplier": multiplier,
    }


# ── Export endpoints ─────────────────────────────────────────────────

@router.get("/export/signals")
async def export_signals(api_key: str = Depends(verify_api_key)):
    """Export all signals as JSON."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM signals ORDER BY original_timestamp DESC").fetchall()
    return {"signals": [_row_to_dict(r) for r in rows], "total": len(rows)}


@router.get("/export/callers")
async def export_callers(api_key: str = Depends(verify_api_key)):
    """Export all callers with aggregated stats as JSON."""
    with get_connection() as conn:
        rows = conn.execute("""
            SELECT
                sender_id,
                sender_name,
                COUNT(*) as total_signals,
                SUM(CASE WHEN status = 'win' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN status = 'loss' THEN 1 ELSE 0 END) as losses,
                ROUND(AVG(CASE WHEN multiplier IS NOT NULL THEN multiplier END), 3) as avg_multiplier,
                MAX(original_timestamp) as last_signal_at
            FROM signals
            WHERE sender_id IS NOT NULL
            GROUP BY sender_id
            ORDER BY total_signals DESC
        """).fetchall()
    callers = []
    for r in rows:
        d = _row_to_dict(r)
        total_checked = (d["wins"] or 0) + (d["losses"] or 0)
        d["win_rate"] = round((d["wins"] / total_checked * 100) if total_checked > 0 else 0, 1)
        callers.append(d)
    return {"callers": callers, "total": len(callers)}
