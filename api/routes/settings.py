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
    mc_threshold: Optional[float] = None
    forward_delay: Optional[float] = None
    max_signals: Optional[int] = None
    display_timezone: Optional[str] = None
    runner_velocity_min: Optional[float] = None
    runner_vol_accel_min: Optional[float] = None
    runner_poll_interval: Optional[int] = None
    source_groups: Optional[list] = None
    report_destination: Optional[str] = None


class BlockCallerRequest(BaseModel):
    sender_id: int
    reason: Optional[str] = None


class UnblockCallerRequest(BaseModel):
    sender_id: int


class BoostCallerRequest(BaseModel):
    sender_id: int
    multiplier: float


class BlacklistAddRequest(BaseModel):
    address: str
    chain: Optional[str] = None
    reason: Optional[str] = None


class SignalStatusOverride(BaseModel):
    new_status: str


class SignalNoteRequest(BaseModel):
    note: str


# ── Helper: read settings with runtime overrides ─────────────────────

SETTINGS_KEYS = {
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
        if k in ("mc_threshold", "forward_delay", "runner_velocity_min", "runner_vol_accel_min"):
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


# ── 1. GET /api/settings/ ────────────────────────────────────────────

@router.get("/")
async def get_settings(api_key: str = Depends(verify_api_key)):
    """Return all current bot settings."""
    return {"settings": _get_all_settings()}


# ── 2. POST /api/settings/ ──────────────────────────────────────────

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


# ── 3. GET /api/settings/health ──────────────────────────────────────

@router.get("/health")
async def system_health(api_key: str = Depends(verify_api_key)):
    """System health check with DB stats, Redis status, and uptime estimate."""
    db_stats = {}
    with get_connection() as conn:
        db_stats["total_signals"] = conn.execute("SELECT COUNT(*) as cnt FROM signals").fetchone()["cnt"]

        # Total unique callers
        db_stats["total_callers"] = conn.execute(
            "SELECT COUNT(DISTINCT sender_id) as cnt FROM signals WHERE sender_id IS NOT NULL"
        ).fetchone()["cnt"]

        # Portfolio entries (table may not exist)
        try:
            db_stats["portfolio_entries"] = conn.execute(
                "SELECT COUNT(*) as cnt FROM portfolio"
            ).fetchone()["cnt"]
        except Exception:
            db_stats["portfolio_entries"] = 0

        # First signal today for uptime estimate
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0, tzinfo=None
        ).isoformat()
        first_today = conn.execute(
            "SELECT MIN(original_timestamp) as ts FROM signals WHERE original_timestamp >= ?",
            (today_start,),
        ).fetchone()

    # DB file size
    try:
        db_stats["db_file_size_mb"] = round(os.path.getsize(DB_FILE) / (1024 * 1024), 2)
    except OSError:
        db_stats["db_file_size_mb"] = None

    # Uptime estimate
    uptime_seconds = None
    if first_today and first_today["ts"]:
        first_ts = datetime.fromisoformat(first_today["ts"])
        uptime_seconds = int((datetime.now(timezone.utc).replace(tzinfo=None) - first_ts).total_seconds())

    # Redis status
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


# ── 4-7. Caller management ──────────────────────────────────────────

@router.get("/callers/blocked")
async def list_blocked_callers(api_key: str = Depends(verify_api_key)):
    """List all blocked callers."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM blocked_callers ORDER BY blocked_at DESC").fetchall()
    return {"blocked_callers": [_row_to_dict(r) for r in rows]}


@router.post("/callers/block")
async def block_caller(body: BlockCallerRequest, api_key: str = Depends(verify_api_key)):
    """Block a caller by sender_id."""
    now = utcnow_iso()
    with get_connection() as conn:
        # Try to get sender name from signals
        name_row = conn.execute(
            "SELECT sender_name FROM signals WHERE sender_id = ? AND sender_name IS NOT NULL LIMIT 1",
            (body.sender_id,),
        ).fetchone()
        sender_name = name_row["sender_name"] if name_row else None

        conn.execute(
            """INSERT INTO blocked_callers (sender_id, sender_name, reason, blocked_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(sender_id) DO UPDATE SET reason = excluded.reason, blocked_at = excluded.blocked_at""",
            (body.sender_id, sender_name, body.reason, now),
        )
        conn.commit()
    return {"status": "blocked", "sender_id": body.sender_id}


@router.post("/callers/unblock")
async def unblock_caller(body: UnblockCallerRequest, api_key: str = Depends(verify_api_key)):
    """Unblock a caller by sender_id."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM blocked_callers WHERE sender_id = ?", (body.sender_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Caller not found in blocklist")
    return {"status": "unblocked", "sender_id": body.sender_id}


@router.post("/callers/boost")
async def boost_caller(body: BoostCallerRequest, api_key: str = Depends(verify_api_key)):
    """Set a score multiplier for a caller (stored in bot_settings as caller_boost:<sender_id>)."""
    now = utcnow_iso()
    key = f"caller_boost:{body.sender_id}"
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO bot_settings (key, value, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at""",
            (key, str(body.multiplier), now),
        )
        conn.commit()
    return {"status": "boosted", "sender_id": body.sender_id, "multiplier": body.multiplier}


# ── 8-10. Contract blacklist ─────────────────────────────────────────

@router.get("/blacklist")
async def list_blacklist(api_key: str = Depends(verify_api_key)):
    """List all blacklisted contract addresses."""
    with get_connection() as conn:
        rows = conn.execute("SELECT * FROM contract_blacklist ORDER BY added_at DESC").fetchall()
    return {"blacklist": [_row_to_dict(r) for r in rows]}


@router.post("/blacklist")
async def add_to_blacklist(body: BlacklistAddRequest, api_key: str = Depends(verify_api_key)):
    """Add a contract address to the blacklist."""
    now = utcnow_iso()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO contract_blacklist (address, chain, reason, added_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(address) DO UPDATE SET chain = excluded.chain, reason = excluded.reason, added_at = excluded.added_at""",
            (body.address.strip().lower(), body.chain, body.reason, now),
        )
        conn.commit()
    return {"status": "blacklisted", "address": body.address.strip().lower()}


@router.delete("/blacklist/{address}")
async def remove_from_blacklist(address: str, api_key: str = Depends(verify_api_key)):
    """Remove a contract address from the blacklist."""
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM contract_blacklist WHERE address = ?", (address.strip().lower(),))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Address not found in blacklist")
    return {"status": "removed", "address": address.strip().lower()}


# ── 11-13. Signal operations ─────────────────────────────────────────

@router.post("/signals/{signal_id}/status")
async def override_signal_status(signal_id: int, body: SignalStatusOverride, api_key: str = Depends(verify_api_key)):
    """Override signal status (win/loss/active)."""
    if body.new_status not in ("win", "loss", "active"):
        raise HTTPException(status_code=400, detail="Status must be one of: win, loss, active")

    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    with get_connection() as conn:
        conn.execute("UPDATE signals SET status = ?, outcome = ? WHERE id = ?", (body.new_status, body.new_status, signal_id))
        conn.commit()
    return {"status": "updated", "signal_id": signal_id, "new_status": body.new_status}


@router.delete("/signals/{signal_id}")
async def delete_signal(signal_id: int, api_key: str = Depends(verify_api_key)):
    """Delete a signal from the database."""
    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    with get_connection() as conn:
        conn.execute("DELETE FROM signal_notes WHERE signal_id = ?", (signal_id,))
        conn.execute("DELETE FROM signals WHERE id = ?", (signal_id,))
        conn.commit()
    return {"status": "deleted", "signal_id": signal_id}


@router.post("/signals/{signal_id}/note")
async def add_signal_note(signal_id: int, body: SignalNoteRequest, api_key: str = Depends(verify_api_key)):
    """Add a note to a signal."""
    row = get_signal_by_id(signal_id)
    if not row:
        raise HTTPException(status_code=404, detail="Signal not found")

    now = utcnow_iso()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO signal_notes (signal_id, note, created_at) VALUES (?, ?, ?)",
            (signal_id, body.note, now),
        )
        conn.commit()
    return {"status": "note_added", "signal_id": signal_id}


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

    # Update signal with fresh data
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


# ── 14-15. Export endpoints ──────────────────────────────────────────

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
