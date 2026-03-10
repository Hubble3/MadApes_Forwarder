"""Performance service - 1h/6h/daily checks as a standalone service."""
import asyncio
import logging

from db import (
    get_signals_to_check_1h,
    get_signals_to_check_6h,
    mark_signal_checked_1h,
    mark_signal_checked_6h,
    update_signal_performance,
)
from madapes.event_bus import emit
from madapes.events import PerformanceChecked
from madapes.formatting import safe_float
from madapes.services.caller_service import update_caller_stats
from madapes.services.enrichment_service import enrich_signal_data
from madapes.services.portfolio_service import update_position, close_position

logger = logging.getLogger(__name__)


async def check_signal_price(signal_row) -> dict | None:
    """Check current price for a signal. Returns check result dict or None."""
    try:
        token_address = signal_row["token_address"]
        token_type = signal_row["token_type"]
        chain = signal_row["chain"]
        ticker = signal_row["ticker"]

        current_data = await enrich_signal_data(chain, token_address, token_type, ticker)
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
                    conn.commit()
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


async def run_1h_checks() -> list:
    """Run 1-hour checks on all eligible signals.
    Returns list of (signal_row, check_result) for winners.
    """
    signals = get_signals_to_check_1h()
    logger.info(f"1h check: {len(signals)} signals")
    winners = []

    for signal_row in signals:
        signal_id = signal_row["id"]
        check_result = await check_signal_price(signal_row)

        if check_result:
            is_winner = check_result["is_winner"]
            update_signal_performance(signal_id, check_result["current_data"], is_winner, time_label="1h")
            mark_signal_checked_1h(signal_id)

            # Emit event
            await emit(PerformanceChecked(
                signal_id=signal_id,
                token_address=signal_row["token_address"],
                time_label="1h",
                is_winner=is_winner,
                price_change=check_result["price_change"],
                multiplier=check_result["multiplier"],
                current_price=safe_float(check_result["current_data"].get("price")),
                current_market_cap=safe_float(check_result["current_data"].get("fdv")),
            ))

            # Update caller stats
            sender_id = signal_row["sender_id"]
            if sender_id:
                update_caller_stats(sender_id, signal_row["sender_name"] or "")

            # Update portfolio position
            current_price = safe_float(check_result["current_data"].get("price"))
            if current_price:
                update_position(signal_id, current_price)

            if is_winner:
                winners.append((signal_row, check_result))

        await asyncio.sleep(1)

    return winners


async def run_6h_checks() -> list:
    """Run 6-hour checks on all eligible signals.
    Returns list of (signal_row, check_result) for winners.
    """
    signals = get_signals_to_check_6h()
    logger.info(f"6h check: {len(signals)} signals")
    winners = []

    for signal_row in signals:
        signal_id = signal_row["id"]
        check_result = await check_signal_price(signal_row)

        if check_result:
            is_winner = check_result["is_winner"]
            update_signal_performance(signal_id, check_result["current_data"], is_winner, time_label="6h")
            mark_signal_checked_6h(signal_id)

            await emit(PerformanceChecked(
                signal_id=signal_id,
                token_address=signal_row["token_address"],
                time_label="6h",
                is_winner=is_winner,
                price_change=check_result["price_change"],
                multiplier=check_result["multiplier"],
                current_price=safe_float(check_result["current_data"].get("price")),
                current_market_cap=safe_float(check_result["current_data"].get("fdv")),
            ))

            # Update caller stats
            sender_id = signal_row["sender_id"]
            if sender_id:
                update_caller_stats(sender_id, signal_row["sender_name"] or "")

            # Close portfolio position at 6h mark
            current_price = safe_float(check_result["current_data"].get("price"))
            if current_price:
                close_position(signal_id, current_price)

            if is_winner:
                winners.append((signal_row, check_result))

        await asyncio.sleep(1)

    return winners
