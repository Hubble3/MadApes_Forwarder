"""Early momentum confirmation — re-checks signals at 5min and 15min marks.

Background task that confirms whether a recently detected signal is actually
running or fading. Sends alerts for confirmed runners and warnings for dumps.
"""
import asyncio
import html
import logging
from datetime import timedelta

from db import get_connection
from utils import utcnow_naive, utcnow_iso
from madapes.constants import CHAIN_EMOJI_MAP, CHAIN_INFO
from madapes.formatting import (
    format_currency,
    format_price,
    safe_float,
    token_display_label,
)
from madapes.message_builder import resolve_report_links
from madapes.services.enrichment_service import enrich_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Momentum status thresholds (price change from entry)
# ---------------------------------------------------------------------------
EARLY_RUNNER_THRESHOLD = 100.0   # >= +100%
CONFIRMED_THRESHOLD = 20.0      # >= +20%
HOLDING_FLOOR = -10.0           # >= -10%
FADING_FLOOR = -30.0            # >= -30%
# Below FADING_FLOOR → dumped

STATUS_META = {
    "early_runner": ("\U0001f680", "EARLY RUNNER"),
    "confirmed":   ("\u2705",     "CONFIRMED"),
    "holding":     ("\U0001f7e1", "HOLDING"),
    "fading":      ("\U0001f7e0", "FADING"),
    "dumped":      ("\U0001f534", "DUMPED"),
}


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_signals_for_5min_check() -> list:
    """Get active signals that are 5-8 minutes old and haven't been 5min-checked yet."""
    now = utcnow_naive()
    window_start = now - timedelta(minutes=8)
    window_end = now - timedelta(minutes=5)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active'
              AND original_timestamp BETWEEN ? AND ?
              AND momentum_check_5m IS NULL
            """,
            (window_start.isoformat(), window_end.isoformat()),
        ).fetchall()
    return rows


def get_signals_for_15min_check() -> list:
    """Get active signals that are 15-20 minutes old and haven't been 15min-checked yet."""
    now = utcnow_naive()
    window_start = now - timedelta(minutes=20)
    window_end = now - timedelta(minutes=15)
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM signals
            WHERE status = 'active'
              AND original_timestamp BETWEEN ? AND ?
              AND momentum_check_15m IS NULL
            """,
            (window_start.isoformat(), window_end.isoformat()),
        ).fetchall()
    return rows


def _update_momentum(signal_id: int, check_type: str, status: str, price: float):
    """Persist a momentum check result.

    check_type: '5m' or '15m'
    """
    col_status = f"momentum_check_{check_type}"
    col_price = f"price_{check_type}"
    with get_connection() as conn:
        conn.execute(
            f"UPDATE signals SET {col_status} = ?, {col_price} = ? WHERE id = ?",
            (status, price, signal_id),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Momentum evaluation
# ---------------------------------------------------------------------------

def evaluate_momentum(signal_row, current_data: dict) -> dict:
    """Evaluate current momentum vs entry point.

    Returns dict with status, price_change_pct, current_price, current_mc,
    volume_momentum, emoji, and label.
    """
    original_price = safe_float(signal_row["original_price"])
    current_price = safe_float(current_data.get("price"))
    current_mc = safe_float(current_data.get("fdv")) or safe_float(current_data.get("market_cap"))

    # Volume / MC ratio as a rough momentum gauge
    volume_24h = safe_float(current_data.get("volume_24h"), 0.0)
    volume_momentum = (volume_24h / current_mc) if current_mc and current_mc > 0 else 0.0

    # Compute % change
    if original_price and original_price > 0 and current_price is not None:
        price_change_pct = ((current_price - original_price) / original_price) * 100.0
    else:
        price_change_pct = 0.0

    # Classify
    if price_change_pct >= EARLY_RUNNER_THRESHOLD:
        status = "early_runner"
    elif price_change_pct >= CONFIRMED_THRESHOLD:
        status = "confirmed"
    elif price_change_pct >= HOLDING_FLOOR:
        status = "holding"
    elif price_change_pct >= FADING_FLOOR:
        status = "fading"
    else:
        status = "dumped"

    emoji, label_prefix = STATUS_META[status]
    sign = "+" if price_change_pct >= 0 else ""
    label = f"{label_prefix} \u2014 Price {sign}{price_change_pct:.1f}%"

    return {
        "status": status,
        "price_change_pct": price_change_pct,
        "current_price": current_price,
        "current_mc": current_mc,
        "volume_momentum": volume_momentum,
        "emoji": emoji,
        "label": label,
    }


# ---------------------------------------------------------------------------
# Alert message builder
# ---------------------------------------------------------------------------

def build_momentum_alert(signal_row, momentum_result: dict, check_type: str) -> str:
    """Build HTML alert message for Telegram.

    check_type: '5min' or '15min'
    """
    sections: list[str] = []
    sections.append("\u2501" * 32)

    emoji = momentum_result["emoji"]
    label = momentum_result["label"]
    sections.append(f"\U0001f3af <b>MOMENTUM CHECK \u2014 {html.escape(check_type)}</b>")
    sections.append(f"{emoji} <b>{html.escape(label)}</b>")
    sections.append("")

    # Token info
    chain = (signal_row["chain"] or "").lower()
    chain_emoji = CHAIN_EMOJI_MAP.get(chain, "\U0001f48e")
    chain_label = CHAIN_INFO.get(chain, ("\U0001f537", chain.upper()))[1]
    display = token_display_label(signal_row["token_name"], signal_row["token_symbol"])
    sections.append(f"{chain_emoji} {chain_label} \u00b7 {display}")

    token_address = signal_row["token_address"]
    sections.append(f"\U0001f4cd CA: <code>{html.escape(str(token_address))}</code>")
    sections.append("")

    # Entry vs current
    original_price = safe_float(signal_row["original_price"])
    original_mc = safe_float(signal_row["original_market_cap"])
    current_price = momentum_result["current_price"]
    current_mc = momentum_result["current_mc"]
    pct = momentum_result["price_change_pct"]

    sections.append(
        f"Entry: {format_price(original_price)} | MC {format_currency(original_mc)}"
    )
    sections.append(
        f"Now:   {format_price(current_price)} | MC {format_currency(current_mc)}"
    )

    arrow = "\U0001f4c8" if pct >= 0 else "\U0001f4c9"
    sign = "+" if pct >= 0 else ""
    sections.append(f"{arrow} {sign}{pct:.1f}% in {check_type}")
    sections.append("")

    # DexScreener link
    from madapes.context import app_context as ctx
    ds_link, sig_link = resolve_report_links(
        signal_row,
        str(token_address or ""),
        chain,
        ctx.destination_entity_under_80k,
        ctx.destination_entity_80k_or_more,
    )
    link_parts: list[str] = []
    if ds_link:
        link_parts.append(f'\U0001f517 <a href="{html.escape(str(ds_link))}">DexScreener</a>')
    if sig_link and "t.me" in (sig_link or ""):
        link_parts.append(f'\U0001f4e8 <a href="{html.escape(str(sig_link))}">Original signal</a>')
    if link_parts:
        sections.append(" | ".join(link_parts))

    sections.append("\u2501" * 32)
    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Background loop
# ---------------------------------------------------------------------------

async def _process_signal(signal_row, check_type: str, client, report_destination_entity):
    """Enrich, evaluate, persist, and optionally alert for one signal.

    check_type: '5min' or '15min' (for display) / maps to '5m' or '15m' DB cols.
    """
    col_suffix = "5m" if check_type == "5min" else "15m"
    chain = (signal_row["chain"] or "").lower()
    token_address = signal_row["token_address"]
    signal_id = signal_row["id"]

    try:
        current_data = await enrich_token(chain, token_address)
        if not current_data:
            logger.warning(
                "Momentum %s: no data for signal %s (%s)", check_type, signal_id, token_address
            )
            return

        result = evaluate_momentum(signal_row, current_data)
        current_price = result["current_price"] if result["current_price"] is not None else 0.0
        _update_momentum(signal_id, col_suffix, result["status"], current_price)

        status = result["status"]
        should_alert = False

        if check_type == "5min":
            if status in ("early_runner", "confirmed", "dumped"):
                should_alert = True
        else:  # 15min
            if status == "early_runner":
                should_alert = True
            elif status == "confirmed":
                # Double-confirmed: was already confirmed at 5min
                prev_5m = signal_row["momentum_check_5m"] if "momentum_check_5m" in signal_row.keys() else None
                if prev_5m == "confirmed":
                    result["label"] = "DOUBLE CONFIRMED \u2014 " + result["label"]
                    result["emoji"] = "\u2705\u2705"
                should_alert = True
            elif status == "dumped":
                should_alert = True

        if should_alert and report_destination_entity:
            msg = build_momentum_alert(signal_row, result, check_type)
            await client.send_message(
                report_destination_entity, msg, parse_mode="html", link_preview=False
            )

            # Also send momentum alerts for GOLD-tier signals to the GOLD channel
            from madapes.context import app_context as _ctx
            sig_tier = signal_row["signal_tier"] if "signal_tier" in signal_row.keys() else None
            if sig_tier == "gold" and _ctx.destination_entity_gold and status in ("early_runner", "confirmed"):
                try:
                    gold_msg = "\U0001f947 <b>GOLD MOMENTUM</b>\n\n" + msg
                    await client.send_message(
                        _ctx.destination_entity_gold, gold_msg,
                        parse_mode="html", link_preview=False,
                    )
                except Exception:
                    pass

    except Exception:
        logger.exception(
            "Momentum %s check failed for signal %s", check_type, signal_id
        )


async def momentum_confirmation_loop(client, report_destination_entity):
    """Background task: checks signals at 5min and 15min marks.

    Runs every 30 seconds, never exits.
    """
    logger.info("Momentum confirmation loop started.")

    while True:
        try:
            # --- 5-minute checks ---
            signals_5m = get_signals_for_5min_check()
            if signals_5m:
                logger.info("Momentum 5min: %d signal(s) to check", len(signals_5m))
            for sig in signals_5m:
                await _process_signal(sig, "5min", client, report_destination_entity)
                await asyncio.sleep(1)  # rate-limit enrichment calls

            # --- 15-minute checks ---
            signals_15m = get_signals_for_15min_check()
            if signals_15m:
                logger.info("Momentum 15min: %d signal(s) to check", len(signals_15m))
            for sig in signals_15m:
                await _process_signal(sig, "15min", client, report_destination_entity)
                await asyncio.sleep(1)

        except Exception:
            logger.exception("Unexpected error in momentum confirmation loop")

        await asyncio.sleep(30)
