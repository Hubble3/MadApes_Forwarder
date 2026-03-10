"""
Real-time runner detection for MadApes Forwarder.
Multi-timeframe momentum detection with tiered alerts and exit signals.
"""
import asyncio
import html
import logging
import time
from datetime import datetime

from madapes.runtime_settings import (
    get_runner_velocity_min, get_runner_vol_accel_min, get_runner_poll_interval,
    get_runner_exit_drawdown_pct, get_runner_exit_liq_drain_pct, get_runner_dedup_window,
)
from db import get_signals_for_runner_check, get_runner_exit_candidates, mark_runner_alerted, mark_exit_alerted, update_max_tracking, check_tp_milestones
from madapes.constants import CHAIN_EMOJI_MAP
from madapes.event_bus import emit
from madapes.events import RunnerDetected
from madapes.formatting import safe_float, format_currency, format_price, format_called_time, token_display_label
from madapes.services.enrichment_service import enrich_token
from utils import utcnow_naive

logger = logging.getLogger(__name__)

# Runner tier thresholds (static upper tiers)
TIER_MOONSHOT_VELOCITY = 5.0    # %/min
TIER_STRONG_VELOCITY = 3.0     # %/min
TIER_MOONSHOT_CHANGE = 200.0   # % price change
TIER_STRONG_CHANGE = 100.0     # %


def classify_runner_tier(velocity, price_change_pct, vol_accel):
    """Classify runner into tiers: moonshot, strong_runner, runner, or None."""
    if velocity >= TIER_MOONSHOT_VELOCITY or price_change_pct >= TIER_MOONSHOT_CHANGE:
        return "moonshot"
    if velocity >= TIER_STRONG_VELOCITY or price_change_pct >= TIER_STRONG_CHANGE:
        return "strong_runner"
    if velocity >= get_runner_velocity_min() and vol_accel >= get_runner_vol_accel_min():
        return "runner"
    return None


def detect_runner(signal_row, current_data):
    """
    Multi-timeframe momentum detection.
    Returns (is_runner: bool, velocity: float, vol_accel: float, details: dict).
    """
    original_price = safe_float(signal_row["original_price"])
    original_volume_24h = safe_float(signal_row["original_volume"], 1.0)
    original_timestamp = signal_row["original_timestamp"]

    current_price = safe_float(current_data.get("price"))
    volume_5m = safe_float(current_data.get("volume_5m"))
    volume_1h = safe_float(current_data.get("volume_1h"))
    volume_24h = safe_float(current_data.get("volume_24h"), 1.0)

    if not original_price or original_price <= 0 or not current_price or current_price <= 0:
        return False, 0.0, 0.0, {}

    try:
        ts = datetime.fromisoformat(original_timestamp.replace("Z", "+00:00"))
        elapsed = (utcnow_naive() - ts.replace(tzinfo=None)).total_seconds()
    except Exception:
        return False, 0.0, 0.0, {}

    minutes = elapsed / 60.0
    if minutes < 1:
        return False, 0.0, 0.0, {}

    price_change_pct = ((current_price - original_price) / original_price) * 100
    velocity = price_change_pct / minutes

    # Volume acceleration: 5m volume annualized vs 24h volume
    if volume_24h and volume_24h > 0 and volume_5m is not None:
        vol_accel = (volume_5m * (24 * 60 / 5)) / volume_24h
    else:
        vol_accel = 0.0

    # Multi-timeframe price changes from DexScreener
    price_change_5m = safe_float(current_data.get("price_change_5m"), 0.0)
    price_change_1h = safe_float(current_data.get("price_change_1h"), 0.0)

    # Volume profile: 5m vol vs 1h average (per 5min bucket)
    vol_profile = 0.0
    if volume_1h and volume_1h > 0 and volume_5m is not None:
        avg_5m_bucket = volume_1h / 12.0  # 12 five-minute buckets per hour
        vol_profile = volume_5m / avg_5m_bucket if avg_5m_bucket > 0 else 0.0

    # Acceleration detection: is the 5m change accelerating vs 1h trend?
    is_accelerating = False
    if price_change_1h and abs(price_change_1h) > 0:
        # If 5m change is in the same direction and proportionally larger
        if price_change_5m > 0 and price_change_1h > 0:
            expected_5m = price_change_1h / 12.0
            is_accelerating = price_change_5m > expected_5m * 2

    is_runner = velocity >= get_runner_velocity_min() and vol_accel >= get_runner_vol_accel_min()
    tier = classify_runner_tier(velocity, price_change_pct, vol_accel)
    if tier is not None:
        is_runner = True

    details = {
        "price_change_pct": price_change_pct,
        "price_change_5m": price_change_5m,
        "price_change_1h": price_change_1h,
        "vol_profile": vol_profile,
        "is_accelerating": is_accelerating,
        "tier": tier or "runner",
        "elapsed_minutes": minutes,
    }

    return is_runner, velocity, vol_accel, details


def detect_exit_signal(signal_row, current_data):
    """Detect potential exit signals: velocity reversal, volume collapse, liquidity drain.
    Returns (should_exit: bool, reason: str).
    """
    max_price = safe_float(signal_row["max_price_seen"])
    current_price = safe_float(current_data.get("price"))
    original_liquidity = safe_float(signal_row["original_liquidity"])
    current_liquidity = safe_float(current_data.get("liquidity"))

    if not current_price or not max_price or max_price <= 0:
        return False, ""

    # Drawdown from peak (configurable threshold)
    drawdown_pct = ((max_price - current_price) / max_price) * 100
    exit_drawdown = get_runner_exit_drawdown_pct()
    if drawdown_pct >= exit_drawdown:
        return True, f"Drawdown {drawdown_pct:.0f}% from peak"

    # Liquidity drain (configurable threshold)
    exit_liq_drain = get_runner_exit_liq_drain_pct()
    if original_liquidity and original_liquidity > 0 and current_liquidity is not None:
        liq_change = ((current_liquidity - original_liquidity) / original_liquidity) * 100
        if liq_change <= -exit_liq_drain:
            return True, f"Liquidity drain {liq_change:.0f}%"

    # Volume collapse: 5m volume near zero when price was running
    price_change_5m = safe_float(current_data.get("price_change_5m"), 0.0)
    volume_5m = safe_float(current_data.get("volume_5m"), 0.0)
    if drawdown_pct >= 15 and price_change_5m < -5 and volume_5m < 100:
        return True, "Volume collapse + reversal"

    return False, ""


TIER_LABELS = {
    "moonshot": "\U0001f680 <b>MOONSHOT DETECTED</b>",
    "strong_runner": "\U0001f525\U0001f525 <b>STRONG RUNNER</b>",
    "runner": "\U0001f525 <b>RUNNER DETECTED</b>",
}

TIER_EXIT = "\U0001f6a8 <b>EXIT SIGNAL</b>"


def build_runner_alert_message(signal_row, current_data, velocity, vol_accel, details=None):
    """Build the runner alert message for REPORT_DESTINATION."""
    token_address = signal_row["token_address"]
    chain = (signal_row["chain"] or "").lower()
    original_price = safe_float(signal_row["original_price"])
    original_market_cap = safe_float(signal_row["original_market_cap"])
    original_timestamp = signal_row["original_timestamp"]

    current_price = safe_float(current_data.get("price"))
    current_market_cap = safe_float(current_data.get("fdv"))

    chain_emoji = CHAIN_EMOJI_MAP.get(chain, "\U0001f48e")
    token_label = token_display_label(signal_row["token_name"], signal_row["token_symbol"])

    called_time = format_called_time(original_timestamp)
    price_change_pct = details.get("price_change_pct", 0.0) if details else 0.0
    if not details and original_price and original_price > 0 and current_price:
        price_change_pct = ((current_price - original_price) / original_price) * 100

    tier = (details or {}).get("tier", "runner")
    header = TIER_LABELS.get(tier, TIER_LABELS["runner"])

    max_price = safe_float(signal_row["max_price_seen"])
    max_mc = safe_float(signal_row["max_market_cap_seen"])

    lines = [
        "\u2501" * 32,
        header,
        "",
        f"{chain_emoji} {(chain or 'CHAIN').upper()} \u00b7 {token_label}",
        f"\U0001f4cd CA (tap to copy): <code>{html.escape(str(token_address))}</code>",
        "",
        f"Entry: {called_time} | {format_price(original_price)} | MC {format_currency(original_market_cap)}",
    ]
    if max_price and max_price > original_price:
        peak_line = f"\U0001f31f ATH:   {format_price(max_price)}"
        if max_mc:
            peak_line += f" | MC {format_currency(max_mc)}"
        lines.append(peak_line)
    lines.extend([
        f"Now:   {format_price(current_price)} | MC {format_currency(current_market_cap)}",
        "",
        f"\U0001f4c8 {price_change_pct:+.1f}% | {velocity:.2f}%/min velocity",
        f"\U0001f4b9 Vol 5m: {vol_accel:.1f}\u00d7 24h rate",
    ])

    # Extra details for strong/moonshot
    if details:
        extra = []
        if details.get("is_accelerating"):
            extra.append("\u26a1 Accelerating")
        if details.get("vol_profile", 0) >= 3.0:
            extra.append(f"\U0001f4ca Vol spike: {details['vol_profile']:.1f}x avg")
        elapsed = details.get("elapsed_minutes", 0)
        if elapsed:
            extra.append(f"\u23f1 {elapsed:.0f}min since signal")
        if extra:
            lines.append(" | ".join(extra))

    lines.append("")

    sig_link = signal_row["signal_link"]
    ds_link = signal_row["original_dexscreener_link"]
    if sig_link:
        lines.append(f'\U0001f517 Signal: <a href="{html.escape(str(sig_link))}">Original alert</a>')
    if ds_link:
        lines.append(f'\U0001f4ca DexScreener: <a href="{html.escape(str(ds_link))}">Chart</a>')
    lines.append("\u2501" * 32)

    return "\n".join(lines)


def build_exit_alert_message(signal_row, current_data, reason):
    """Build exit signal alert message."""
    token_address = signal_row["token_address"]
    chain = (signal_row["chain"] or "").lower()
    original_price = safe_float(signal_row["original_price"])
    max_price = safe_float(signal_row["max_price_seen"])
    current_price = safe_float(current_data.get("price"))
    current_market_cap = safe_float(current_data.get("fdv"))

    chain_emoji = CHAIN_EMOJI_MAP.get(chain, "\U0001f48e")
    token_label = token_display_label(signal_row["token_name"], signal_row["token_symbol"])

    price_change_pct = 0.0
    if original_price and original_price > 0 and current_price:
        price_change_pct = ((current_price - original_price) / original_price) * 100

    lines = [
        "\u2501" * 32,
        TIER_EXIT,
        "",
        f"{chain_emoji} {(chain or 'CHAIN').upper()} \u00b7 {token_label}",
        f"\U0001f4cd CA: <code>{html.escape(str(token_address))}</code>",
        "",
        f"Entry: {format_price(original_price)} | ATH: {format_price(max_price)} | Now: {format_price(current_price)}",
        f"MC: {format_currency(current_market_cap)} | P&L: {price_change_pct:+.1f}%",
        "",
        f"\u26a0\ufe0f Reason: {reason}",
        "\u2501" * 32,
    ]
    return "\n".join(lines)


def build_tp_alert_line(signal_row, tp_labels, current_price):
    """Build a single line for the TP milestone summary."""
    chain_emoji = CHAIN_EMOJI_MAP.get((signal_row["chain"] or "").lower(), "\U0001f48e")
    token_label = token_display_label(signal_row["token_name"], signal_row["token_symbol"])
    original_price = safe_float(signal_row["original_price"])
    gain_pct = ((current_price - original_price) / original_price * 100) if original_price and original_price > 0 else 0
    tp_text = ", ".join(tp_labels)
    return f"{chain_emoji} {token_label} hit <b>{tp_text}</b> ({gain_pct:+.0f}% from entry)"


async def runner_watcher(client, report_destination_entity):
    """Main loop: poll for runner candidates every poll_interval seconds."""

    logger.info("Runner watcher started")

    # Dedup: track recently alerted tokens by address → {tier: timestamp}
    _recent_alerts: dict[str, dict[str, float]] = {}

    def _is_duplicate(token_address: str, tier: str) -> bool:
        """Check if this token+tier was already alerted within the dedup window."""
        window = get_runner_dedup_window()
        now = time.monotonic()
        entry = _recent_alerts.get(token_address)
        if entry and tier in entry:
            if now - entry[tier] < window:
                return True
        return False

    def _mark_alerted(token_address: str, tier: str):
        """Record that we alerted this token+tier."""
        now = time.monotonic()
        if token_address not in _recent_alerts:
            _recent_alerts[token_address] = {}
        _recent_alerts[token_address][tier] = now

    def _cleanup_dedup():
        """Remove expired dedup entries."""
        window = get_runner_dedup_window()
        now = time.monotonic()
        expired = []
        for addr, tiers in _recent_alerts.items():
            tiers_to_remove = [t for t, ts in tiers.items() if now - ts >= window]
            for t in tiers_to_remove:
                del tiers[t]
            if not tiers:
                expired.append(addr)
        for addr in expired:
            del _recent_alerts[addr]

    while True:
        try:
            _cleanup_dedup()
            _tp_alerts = []

            signals = get_signals_for_runner_check()
            if signals:
                logger.debug(f"Runner check: {len(signals)} signal(s) in window")

            for signal_row in signals:
                signal_id = signal_row["id"]
                chain = signal_row["chain"]
                token_address = signal_row["token_address"]

                try:
                    current_data = await enrich_token(chain, token_address)
                    if not current_data or not current_data.get("price"):
                        continue

                    is_runner, velocity, vol_accel, details = detect_runner(signal_row, current_data)

                    current_price = safe_float(current_data.get("price"))
                    current_mc = safe_float(current_data.get("fdv"))
                    update_max_tracking(signal_id, current_price, current_mc)

                    # Check take-profit milestones
                    if current_price:
                        new_tps = check_tp_milestones(signal_id, current_price)
                        if new_tps:
                            _tp_alerts.append(build_tp_alert_line(signal_row, new_tps, current_price))

                    if is_runner:
                        tier = details.get("tier", "runner")

                        # Dedup: skip if same token+tier already alerted recently
                        if _is_duplicate(token_address, tier):
                            logger.debug(f"Dedup: skipping {tier} alert for {token_address[:8]}... (already sent)")
                            mark_runner_alerted(signal_id)
                            continue

                        price_change_pct = details.get("price_change_pct", 0.0)
                        await emit(RunnerDetected(
                            signal_id=signal_id,
                            token_address=token_address,
                            chain=chain,
                            velocity=velocity,
                            vol_accel=vol_accel,
                            price_change_pct=price_change_pct,
                            token_name=signal_row["token_name"] or "",
                            token_symbol=signal_row["token_symbol"] or "",
                        ))

                        if report_destination_entity is None:
                            logger.warning("Runner detected but REPORT_DESTINATION not set")
                        else:
                            msg = build_runner_alert_message(signal_row, current_data, velocity, vol_accel, details)
                            await client.send_message(
                                report_destination_entity, msg,
                                parse_mode="html", link_preview=False,
                            )
                            mark_runner_alerted(signal_id)
                            _mark_alerted(token_address, tier)
                            logger.info(f"{tier.upper()} alert sent for signal {signal_id} ({token_address[:8]}...)")

                            # Also send runner alerts for GOLD-tier signals to the GOLD channel
                            from madapes.context import app_context as _ctx
                            signal_tier = signal_row["signal_tier"] if "signal_tier" in signal_row.keys() else None
                            if signal_tier == "gold" and _ctx.destination_entity_gold:
                                try:
                                    gold_msg = "\U0001f947 <b>GOLD RUNNER ALERT</b>\n\n" + msg
                                    await client.send_message(
                                        _ctx.destination_entity_gold, gold_msg,
                                        parse_mode="html", link_preview=False,
                                    )
                                except Exception:
                                    pass

                except Exception as e:
                    logger.error(f"Runner check failed for signal {signal_id}: {e}")

                await asyncio.sleep(1.5)

            # Exit signal detection — batched into a single summary message
            exit_candidates = get_runner_exit_candidates()
            exit_entries = []
            for signal_row in exit_candidates:
                signal_id = signal_row["id"]
                try:
                    current_data = await enrich_token(signal_row["chain"], signal_row["token_address"])
                    if not current_data or not current_data.get("price"):
                        continue

                    current_price = safe_float(current_data.get("price"))
                    current_mc = safe_float(current_data.get("fdv"))
                    update_max_tracking(signal_id, current_price, current_mc)

                    # Check TPs for exit candidates too
                    if current_price:
                        new_tps = check_tp_milestones(signal_id, current_price)
                        if new_tps:
                            _tp_alerts.append(build_tp_alert_line(signal_row, new_tps, current_price))

                    should_exit, exit_reason = detect_exit_signal(signal_row, current_data)
                    if should_exit:
                        chain_emoji = CHAIN_EMOJI_MAP.get((signal_row["chain"] or "").lower(), "\U0001f48e")
                        label = token_display_label(signal_row["token_name"], signal_row["token_symbol"])
                        exit_entries.append(f"{chain_emoji} {label} \u2014 {exit_reason}")
                        mark_exit_alerted(signal_id)
                        logger.info(f"Exit signal for {signal_id}: {exit_reason}")
                except Exception as e:
                    logger.error(f"Exit signal check failed for signal {signal_id}: {e}")

                await asyncio.sleep(1.5)

            # Send consolidated TP milestone alerts
            if _tp_alerts and report_destination_entity:
                lines = ["\u2501" * 32, "\U0001f3af <b>TAKE-PROFIT MILESTONES</b>", ""]
                for entry in _tp_alerts:
                    lines.append(f"\u2022 {entry}")
                lines.append("")
                lines.append("\u2501" * 32)
                try:
                    await client.send_message(
                        report_destination_entity, "\n".join(lines),
                        parse_mode="html", link_preview=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send TP alert: {e}")

            # Send consolidated exit summary
            if exit_entries and report_destination_entity:
                lines = ["\u2501" * 32, "\U0001f6a8 <b>EXIT SIGNALS</b>", ""]
                for entry in exit_entries:
                    lines.append(f"\u2022 {entry}")
                lines.append("")
                lines.append("\u2501" * 32)
                try:
                    await client.send_message(
                        report_destination_entity, "\n".join(lines),
                        parse_mode="html", link_preview=False,
                    )
                except Exception as e:
                    logger.error(f"Failed to send exit summary: {e}")

        except Exception as e:
            logger.error(f"Runner watcher error: {e}")

        await asyncio.sleep(get_runner_poll_interval())
