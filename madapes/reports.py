"""Daily report, 1h/6h performance updates, new day broadcast."""
import asyncio
import html
import logging
from datetime import datetime

from analytics import build_daily_analytics_block, run_daily_analytics
from config import MAX_SIGNALS
from db import (
    delete_losing_signals,
    enforce_capacity,
    get_all_active_signals,
    get_signals_count,
)
from dexscreener import fetch_token_data as fetch_dexscreener_data
from madapes.context import app_context
from madapes.constants import CHAIN_EMOJI_MAP
from madapes.formatting import (
    format_called_time,
    format_currency,
    format_price,
    safe_float,
    token_display_label,
)
from madapes.message_builder import resolve_report_links
from madapes.services.leaderboard_service import get_caller_leaderboard, get_performance_attribution
from madapes.services.performance_service import check_signal_price, run_1h_checks, run_6h_checks
from madapes.services.portfolio_service import get_portfolio_summary

logger = logging.getLogger(__name__)


def _entity_label(entity, fallback="unknown"):
    if entity is None:
        return fallback
    try:
        if hasattr(entity, "title") and entity.title:
            return entity.title
        if hasattr(entity, "username") and entity.username:
            return f"@{entity.username}"
        if hasattr(entity, "first_name"):
            name = f"{entity.first_name or ''} {getattr(entity, 'last_name', '') or ''}".strip()
            return name or "Saved Messages"
    except Exception:
        pass
    return str(entity)


async def check_signal_price(signal_row):
    """Check current price for a signal and determine if it's a winner."""
    try:
        token_address = signal_row["token_address"]
        token_type = signal_row["token_type"]
        chain = signal_row["chain"]
        ticker = signal_row["ticker"]

        if token_type == "contract":
            current_data = await fetch_dexscreener_data(chain, token_address)
        else:
            from dexscreener import fetch_ticker_data as fetch_dexscreener_ticker_data
            current_data = await fetch_dexscreener_ticker_data(ticker)

        if not current_data or not current_data.get("price"):
            return None

        original_price = safe_float(signal_row["original_price"])

        # Auto-fill missing entry price from first available live data
        if (not original_price or original_price <= 0) and current_data.get("price"):
            original_price = float(current_data["price"])
            try:
                from db import get_connection
                with get_connection() as conn:
                    conn.execute(
                        """UPDATE signals SET original_price = ?, original_market_cap = COALESCE(original_market_cap, ?),
                           original_liquidity = COALESCE(original_liquidity, ?), original_volume = COALESCE(original_volume, ?)
                        WHERE id = ? AND original_price IS NULL""",
                        (original_price,
                         float(current_data["fdv"]) if current_data.get("fdv") else None,
                         float(current_data["liquidity"]) if current_data.get("liquidity") else None,
                         float(current_data["volume_24h"]) if current_data.get("volume_24h") else None,
                         signal_row["id"]),
                    )
                    conn.commit()
                logger.info(f"Auto-filled entry price for signal {signal_row['id']}: ${original_price}")
            except Exception as e:
                logger.debug(f"Auto-fill entry price failed: {e}")
            # On first fill, entry = current, so P&L is 0 — return neutral result
            return {
                "current_data": current_data,
                "price_change": 0.0,
                "multiplier": 1.0,
                "is_winner": False,
            }

        if not original_price or original_price <= 0:
            return None

        current_price = float(current_data["price"])
        price_change = ((current_price - original_price) / original_price) * 100
        is_winner = current_price > original_price

        # Re-enrich missing token name/symbol/chain from DexScreener response
        ds_name = current_data.get("name") or current_data.get("token_name")
        ds_symbol = current_data.get("symbol") or current_data.get("token_symbol")
        ds_chain = current_data.get("chain")
        needs_name = not signal_row["token_name"] or not signal_row["token_symbol"]
        needs_chain = ds_chain and ds_chain != signal_row["chain"]
        if (needs_name and (ds_name or ds_symbol)) or needs_chain:
            try:
                from db import get_connection
                with get_connection() as conn:
                    conn.execute(
                        "UPDATE signals SET token_name=COALESCE(token_name,?), token_symbol=COALESCE(token_symbol,?), chain=COALESCE(?,chain) WHERE id=?",
                        (ds_name, ds_symbol, ds_chain if needs_chain else None, signal_row["id"]),
                    )
                logger.info(f"Re-enriched signal {signal_row['id']}: name={ds_name}, symbol={ds_symbol}, chain={ds_chain}")
            except Exception as e:
                logger.debug(f"Re-enrich update failed: {e}")

        return {
            "current_data": current_data,
            "price_change": price_change,
            "multiplier": current_price / original_price,
            "is_winner": is_winner,
        }
    except Exception as e:
        logger.error(f"Error checking signal price: {e}")
        return None


async def send_performance_update_to_report(signal_row, check_result, time_label):
    """Send a performance update message to REPORT_DESTINATION."""
    try:
        ctx = app_context
        report_dest = ctx.require_report_destination()

        token_address = signal_row["token_address"]
        token_type = signal_row["token_type"]
        chain = signal_row["chain"]
        ticker = signal_row["ticker"]
        original_price = safe_float(signal_row["original_price"])
        original_market_cap = safe_float(signal_row["original_market_cap"])
        original_timestamp = signal_row["original_timestamp"]

        current_data = check_result["current_data"]
        price_change = check_result["price_change"]
        multiplier = check_result["multiplier"]
        is_winner = check_result["is_winner"]
        current_price = safe_float(current_data.get("price"))

        sections = []
        sections.append("\u2501" * 32)
        sections.append(f"\U0001f4ca <b>PERFORMANCE UPDATE ({time_label})</b>")
        sections.append("")

        if token_type == "contract":
            chain_key = (chain or "").lower()
            chain_emoji = CHAIN_EMOJI_MAP.get(chain_key, "\U0001f48e")
            label = token_display_label(signal_row["token_name"], signal_row["token_symbol"])
            sections.append(f"{chain_emoji} {(chain_key or 'CHAIN').upper()} \u00b7 {label}")
            sections.append(f"\U0001f4cd CA (tap to copy): <code>{html.escape(str(token_address))}</code>")
        else:
            sections.append(f"<b>\U0001f4c8 ${ticker}</b>")

        called_time = format_called_time(original_timestamp, ctx.display_tz)
        sections.append(f"Called: <code>{called_time}</code> | Price {format_price(original_price)} | MC {format_currency(original_market_cap)}")
        sections.append("")

        status_emoji = "\U0001f7e2 WINNER" if is_winner else "\U0001f534 LOSER"
        sections.append(f"{status_emoji}: {price_change:+.2f}% ({multiplier:.2f}x)")
        sections.append("")
        sections.append(f"\U0001f4b5 Original: {format_price(original_price)}")
        sections.append(f"\U0001f4b5 Current: {format_price(current_price)}")
        sections.append("")

        metrics = []
        if current_data.get("price_change_24h") is not None:
            change_24h = float(current_data["price_change_24h"])
            emoji_24h = "\U0001f7e2" if change_24h >= 0 else "\U0001f534"
            metrics.append(f"{emoji_24h} 24h: {change_24h:+.2f}%")
        if current_data.get("volume_24h"):
            metrics.append(f"\U0001f4c8 Vol: {format_currency(float(current_data['volume_24h']))}")
        if current_data.get("liquidity"):
            metrics.append(f"\U0001f4a7 Liq: {format_currency(float(current_data['liquidity']))}")
        if current_data.get("fdv"):
            metrics.append(f"\U0001f4ca MC: {format_currency(float(current_data['fdv']))}")
        if metrics:
            sections.append(" | ".join(metrics))

        ds_link, sig_link = resolve_report_links(
            signal_row, str(token_address or ""), chain or "",
            ctx.destination_entity_under_80k, ctx.destination_entity_80k_or_more,
        )
        sections.append("")
        link_parts = []
        if ds_link:
            link_parts.append(f'\U0001f4ca <a href="{html.escape(ds_link)}">DexScreener</a>')
        if sig_link and "t.me" in (sig_link or ""):
            link_parts.append(f'\U0001f517 <a href="{html.escape(sig_link)}">Our alert message</a>')
        if link_parts:
            sections.append(" | ".join(link_parts))

        sections.append("\u2501" * 32)

        await ctx.client.send_message(report_dest, "\n".join(sections), parse_mode="html", link_preview=False)
    except Exception as e:
        logger.error(f"Error sending performance update to report: {e}")


async def check_and_update_signals_1h():
    """Check signals after 1 hour and update if winners."""
    try:
        winners = await run_1h_checks()
        for signal_row, check_result in winners:
            try:
                await send_performance_update_to_report(signal_row, check_result, "1h")
            except Exception as send_err:
                logger.error(f"Failed to send 1h update for signal {signal_row['id']}: {send_err}")
    except Exception as e:
        logger.error(f"Error in 1h check: {e}")


async def check_and_update_signals_6h():
    """Check signals after 6 hours (only winners from 1h)."""
    try:
        winners = await run_6h_checks()
        for signal_row, check_result in winners:
            try:
                await send_performance_update_to_report(signal_row, check_result, "6h")
            except Exception as send_err:
                logger.error(f"Failed to send 6h update for signal {signal_row['id']}: {send_err}")
    except Exception as e:
        logger.error(f"Error in 6h check: {e}")


async def generate_daily_report():
    """Generate and send daily end-of-day report."""
    logger.info("Daily report started")
    try:
        ctx = app_context
        report_dest = ctx.require_report_destination()
        signals = get_all_active_signals()
        if not signals:
            logger.info("Daily report skipped (no signals)")
            return

        maryland_now = datetime.now(ctx.display_tz)
        report_date = maryland_now.strftime("%B %d, %Y")

        def _dedupe_by_token(lst):
            seen = {}
            for s in lst:
                addr = s["token_address"]
                if addr and addr not in seen:
                    seen[addr] = s
                elif not addr:
                    seen[id(s)] = s
            return list(seen.values())

        winners = _dedupe_by_token([s for s in signals if s["status"] == "win"])
        losers = _dedupe_by_token([s for s in signals if s["status"] == "loss"])
        active = _dedupe_by_token([s for s in signals if s["status"] == "active"])

        total_calls = len(winners) + len(losers) + len(active)
        win_count = len(winners)
        loss_count = len(losers)
        active_count = len(active)
        win_rate = (win_count / total_calls * 100) if total_calls else 0

        def token_display(row):
            addr = str(row["token_address"] or "")
            chain = (row["chain"] or "").lower()
            emoji = CHAIN_EMOJI_MAP.get(chain, "\U0001f48e")
            label = token_display_label(row["token_name"], row["token_symbol"])
            return emoji, (chain.upper() if chain else "CHAIN"), label, addr

        def line_checkpoint(prefix, price, mc, change, mult):
            if price is None or mc is None or change is None or mult is None:
                return f"   {prefix}: N/A"
            return f"   {prefix}:     Price {format_price(price)} | MC {format_currency(mc)} | {change:+.2f}% ({mult:.2f}x)"

        report_lines = []
        report_lines.append("\u2501" * 32)
        report_lines.append(f"\U0001f4ca <b>DAILY REPORT \u2014 {report_date} (MD)</b>")
        report_lines.append("")
        report_lines.append("\U0001f4c8 <b>Summary</b>")
        report_lines.append(
            f"Total Calls: {total_calls} | \U0001f7e2 Winners: {win_count} | \U0001f534 Losers: {loss_count} | "
            f"\u26aa Active: {active_count} | Win Rate: {win_rate:.1f}%"
        )
        report_lines.append(f"\U0001f534 Losers: {loss_count} (details hidden)")
        report_lines.append("")

        # Winners
        report_lines.append(f"\U0001f7e2 <b>Winners ({win_count})</b>")
        if not winners:
            report_lines.append("No winners today.")
        else:
            for i, row in enumerate(winners, 1):
                addr = str(row["token_address"])
                chain = (row["chain"] or "").lower()
                emoji, chain_label, label, ca = token_display(row)
                called_time = format_called_time(row["original_timestamp"], ctx.display_tz)
                called_price = safe_float(row["original_price"])
                called_mc = safe_float(row["original_market_cap"])

                price_1h = safe_float(row["price_1h"])
                mc_1h = safe_float(row["market_cap_1h"])
                chg_1h = safe_float(row["price_change_1h"])
                mult_1h = safe_float(row["multiplier_1h"])

                price_6h = safe_float(row["price_6h"])
                mc_6h = safe_float(row["market_cap_6h"])
                chg_6h = safe_float(row["price_change_6h"])
                mult_6h = safe_float(row["multiplier_6h"])

                report_lines.append(f"{i}) {emoji} {chain_label} {label}")
                report_lines.append(f"   CA (tap to copy): <code>{html.escape(ca)}</code>")
                report_lines.append(
                    f"   Called: {called_time} | Price {format_price(called_price)} | MC {format_currency(called_mc)}"
                )
                report_lines.append(line_checkpoint("1h", price_1h, mc_1h, chg_1h, mult_1h))
                if not row["checked_6h"]:
                    report_lines.append("   6h:     (not checked yet)")
                else:
                    report_lines.append(line_checkpoint("6h", price_6h, mc_6h, chg_6h, mult_6h))

                # Live fetch
                live_line = "   Live:   N/A"
                try:
                    live = await fetch_dexscreener_data(chain, addr)
                    live_price = safe_float(live.get("price")) if live else None
                    live_mc = safe_float(live.get("fdv")) if live else None
                    if live_price is not None and live_mc is not None and called_price and called_price > 0:
                        live_chg = ((live_price - called_price) / called_price) * 100
                        live_mult = live_price / called_price
                        live_line = f"   Live:   Price {format_price(live_price)} | MC {format_currency(live_mc)} | {live_chg:+.2f}% ({live_mult:.2f}x)"
                    elif live_price is not None and live_mc is not None:
                        live_line = f"   Live:   Price {format_price(live_price)} | MC {format_currency(live_mc)}"
                except Exception:
                    pass
                report_lines.append(live_line)

                ds_link, sig_link = resolve_report_links(
                    row, addr, chain, ctx.destination_entity_under_80k, ctx.destination_entity_80k_or_more,
                )
                link_parts = []
                if ds_link:
                    link_parts.append(f'\U0001f4ca <a href="{html.escape(ds_link)}">DexScreener</a>')
                if sig_link and "t.me" in (sig_link or ""):
                    link_parts.append(f'\U0001f517 <a href="{html.escape(sig_link)}">Our alert</a>')
                if link_parts:
                    report_lines.append(f"   {' | '.join(link_parts)}")
                report_lines.append("")

        # Active
        report_lines.append(f"\u26aa <b>Active ({active_count})</b>")
        if not active:
            report_lines.append("No active calls.")
        else:
            report_lines.append(f"- Waiting 1h: {len(active)}")
            report_lines.append("")
            max_active_list = 25
            for row in active[:max_active_list]:
                emoji, chain_label, label, ca = token_display(row)
                called_time = format_called_time(row["original_timestamp"], ctx.display_tz)
                called_price = safe_float(row["original_price"])
                called_mc = safe_float(row["original_market_cap"])
                report_lines.append(f"- {emoji} {chain_label} {label}")
                report_lines.append(f"  CA (tap to copy): <code>{html.escape(ca)}</code>")
                report_lines.append(f"  Called: {called_time} | Price {format_price(called_price)} | MC {format_currency(called_mc)} | Status: waiting 1h")
                addr, chain = str(row["token_address"]), (row["chain"] or "").lower()
                ds_link, sig_link = resolve_report_links(
                    row, addr, chain, ctx.destination_entity_under_80k, ctx.destination_entity_80k_or_more,
                )
                link_parts = []
                if ds_link:
                    link_parts.append(f'\U0001f4ca <a href="{html.escape(ds_link)}">DexScreener</a>')
                if sig_link and "t.me" in (sig_link or ""):
                    link_parts.append(f'\U0001f517 <a href="{html.escape(sig_link)}">Our alert</a>')
                if link_parts:
                    report_lines.append(f"  {' | '.join(link_parts)}")
            remaining = len(active) - max_active_list
            if remaining > 0:
                report_lines.append(f"... and {remaining} more active calls")

        # Portfolio P&L Summary
        try:
            portfolio = get_portfolio_summary()
            if portfolio["total_open"] > 0 or portfolio["total_closed"] > 0:
                report_lines.append("")
                report_lines.append("\U0001f4b0 <b>Portfolio P&L</b>")
                pnl_emoji = "\U0001f7e2" if portfolio["total_pnl"] >= 0 else "\U0001f534"
                report_lines.append(
                    f"{pnl_emoji} Total P&L: ${portfolio['total_pnl']:+.2f} | "
                    f"Realized: ${portfolio['total_realized_pnl']:+.2f} | "
                    f"Unrealized: ${portfolio['total_unrealized_pnl']:+.2f}"
                )
                report_lines.append(
                    f"Open: {portfolio['total_open']} | Closed: {portfolio['total_closed']} | "
                    f"WR: {portfolio['win_rate']:.0f}% | Max DD: {portfolio['max_drawdown_pct']:.1f}%"
                )
                if portfolio["total_closed"] > 0:
                    report_lines.append(
                        f"Best: {portfolio['best_pnl_pct']:+.1f}% | Worst: {portfolio['worst_pnl_pct']:+.1f}%"
                    )
                report_lines.append("")
        except Exception as e:
            logger.debug(f"Portfolio summary error: {e}")

        # Top Callers
        try:
            leaderboard = get_caller_leaderboard(window_days=1, limit=5)
            if leaderboard:
                report_lines.append("\U0001f3c6 <b>Top Callers (24h)</b>")
                medals = {1: "\U0001f947", 2: "\U0001f948", 3: "\U0001f949"}
                for entry in leaderboard:
                    medal = medals.get(entry["rank"], f"{entry['rank']}.")
                    avg_emoji = "\U0001f7e2" if entry["avg_return"] >= 0 else "\U0001f534"
                    report_lines.append(
                        f"{medal} {entry['sender_name']} | {avg_emoji} {entry['avg_return']:+.1f}% avg | "
                        f"WR: {entry['win_rate']:.0f}%"
                    )
                report_lines.append("")
        except Exception as e:
            logger.debug(f"Leaderboard error: {e}")

        # Performance Attribution
        try:
            attribution = get_performance_attribution()
            by_chain = attribution.get("by_chain", {})
            if by_chain:
                report_lines.append("\U0001f4ca <b>By Chain</b>")
                for chain_name, stats in list(by_chain.items())[:5]:
                    emoji = "\U0001f7e2" if stats["avg_return"] >= 0 else "\U0001f534"
                    report_lines.append(
                        f"  {(chain_name or '?').upper()}: {emoji} {stats['avg_return']:+.1f}% | "
                        f"WR: {stats['win_rate']:.0f}% ({stats['total']})"
                    )
                report_lines.append("")
        except Exception as e:
            logger.debug(f"Attribution error: {e}")

        # Analytics
        analytics = run_daily_analytics(report_date)
        report_lines.extend(build_daily_analytics_block(analytics))

        # Cleanup
        report_lines.append("")
        report_lines.append("\U0001f9f9 <b>Cleanup</b>")
        deleted_count = delete_losing_signals()
        trimmed = enforce_capacity(MAX_SIGNALS)
        remaining_count = get_signals_count()
        report_lines.append(f"\U0001f5d1\ufe0f Deleted losers: {deleted_count}")
        report_lines.append(f"\U0001f4c9 Capacity trimmed: {trimmed} (max {MAX_SIGNALS})")
        report_lines.append(f"Remaining after cleanup: {remaining_count}")
        report_lines.append("\u2501" * 32)

        report_text = "\n".join(report_lines).strip()

        # Send (split if too long)
        max_len = 3500
        if len(report_text) <= max_len:
            await ctx.client.send_message(report_dest, report_text, parse_mode="html", link_preview=False)
        else:
            chunk = []
            size = 0
            part = 1
            for line in report_lines:
                add = len(line) + 1
                if size + add > max_len and chunk:
                    await ctx.client.send_message(
                        report_dest,
                        "\n".join(chunk) + f"\n\n<b>Part {part}</b>",
                        parse_mode="html", link_preview=False,
                    )
                    part += 1
                    chunk = []
                    size = 0
                chunk.append(line)
                size += add
            if chunk:
                await ctx.client.send_message(
                    report_dest,
                    "\n".join(chunk) + f"\n\n<b>Part {part}</b>",
                    parse_mode="html", link_preview=False,
                )

        logger.info(f"Daily report sent for {report_date}")
    except Exception as e:
        logger.error(f"Daily report failed: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def send_new_day_to_destinations():
    """Send 'NEW DAY' message to signal destinations + report group."""
    try:
        ctx = app_context
        maryland_now = datetime.now(ctx.display_tz)
        date_str = maryland_now.strftime("%A, %B %d, %Y")
        msg = (
            "\u2501" * 32 + "\n"
            f"<b>\U0001f305 NEW DAY \u2014 {date_str}</b>\n"
            + "\u2501" * 32
        )
        sent = 0
        dests = [ctx.destination_entity_under_80k, ctx.destination_entity_80k_or_more]
        if ctx.report_destination_entity is not None:
            dests.append(ctx.report_destination_entity)
        for dest in dests:
            if dest is None:
                continue
            try:
                await ctx.client.send_message(dest, msg, parse_mode="html", link_preview=False)
                sent += 1
                logger.info(f"NEW DAY sent to {_entity_label(dest)}")
            except Exception as e:
                logger.error(f"Failed to send NEW DAY to {_entity_label(dest)}: {e}")
        if sent:
            ctx.last_new_day_date = maryland_now.date()
    except Exception as e:
        logger.error(f"Error sending NEW DAY: {e}")


async def background_checker():
    """Background task that runs price checks periodically."""
    ctx = app_context
    while True:
        try:
            await check_and_update_signals_1h()
            await check_and_update_signals_6h()

            maryland_now = datetime.now(ctx.display_tz)
            today = maryland_now.date()

            if maryland_now.hour == 0 and ctx.last_new_day_date != today:
                await send_new_day_to_destinations()

            if maryland_now.hour == 23 and maryland_now.minute >= 55 and ctx.last_daily_report_date != today:
                await generate_daily_report()
                ctx.last_daily_report_date = today
                await asyncio.sleep(120)

            await asyncio.sleep(300)
        except Exception as e:
            logger.error(f"Error in background checker: {e}")
            await asyncio.sleep(60)
