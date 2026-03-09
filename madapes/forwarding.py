"""Core forward_message logic for MadApes Forwarder."""
import asyncio
import html
import logging
import time

from telethon.errors import ChatAdminRequiredError
from telethon.tl.types import Channel

from madapes.runtime_settings import get_forward_delay, get_mc_threshold
from db import (
    claim_signal_if_new,
    delete_claim,
    mark_source_message_processed,
    update_signal_after_forward,
    update_signal_minimal_after_forward,
    was_token_forwarded_recently,
)
from madapes.constants import DS_CHAINS
from madapes.context import app_context
from madapes.detection import detect_contract_addresses, extract_trading_info
from madapes.event_bus import emit
from madapes.events import SignalDetected, SignalEnriched, SignalForwarded
from madapes.message_builder import (
    build_dexscreener_links,
    build_info_message,
    build_message_link,
    format_timestamp,
)
from madapes.services.caller_service import get_caller_badge, update_caller_stats
from madapes.services.correlation_service import record_caller_for_token
from madapes.services.enrichment_service import enrich_token
from madapes.services.onchain_service import check_token_safety, safety_summary
from madapes.services.portfolio_service import open_position
from madapes.services.scoring_service import compute_signal_confidence, confidence_badge
from madapes.services.tagging_service import compute_tags, tags_display

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


def _message_ids(msgs):
    if msgs is None:
        return []
    if isinstance(msgs, (list, tuple)):
        return [getattr(m, "id", None) for m in msgs if getattr(m, "id", None) is not None]
    mid = getattr(msgs, "id", None)
    return [mid] if mid is not None else []


async def forward_message(message, chat, sender):
    """Forward a message and send info message. Destination chosen by market cap."""
    ctx = app_context
    message_id = message.id
    try:
        if get_forward_delay() > 0:
            await asyncio.sleep(get_forward_delay())

        # Sender info
        sender_id = message.sender_id
        sender_name = "Unknown"
        sender_username = None
        if sender:
            if isinstance(sender, Channel):
                sender_name = getattr(sender, "title", None) or "Channel"
                sender_username = getattr(sender, "username", None)
            elif hasattr(sender, "first_name"):
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"
                sender_username = getattr(sender, "username", None)

        group_name = getattr(chat, "title", None) or getattr(chat, "username", None) or "Unknown"
        message_link = build_message_link(chat, message.id)
        message_text = message.text or message.raw_text or ""

        contract_addresses = detect_contract_addresses(message_text)

        k = ctx.pending_key(chat, message_id)
        if k and contract_addresses:
            ctx.pending_no_contract.pop(k, None)

        if not contract_addresses:
            ctx.prune_pending()
            if k:
                ctx.pending_no_contract.setdefault(k, time.time())
                logger.info(f"Pending edit watch for message {message_id}: no contract yet")
            logger.info(f"Skipping message {message_id}: No contract address detected")
            return False

        chain, address = contract_addresses[0]
        if was_token_forwarded_recently(address, within_seconds=120):
            logger.info(f"Skipping message {message_id}: Same token forwarded recently")
            return False

        chat_id = getattr(chat, "id", None)
        if chat_id is not None and not mark_source_message_processed(chat_id, message_id):
            logger.info(f"Skipping message {message_id}: Already processed")
            return False

        claim_id = claim_signal_if_new(
            address, chain, message_id, group_name, sender_id, sender_name,
            all_addresses=contract_addresses,
        )
        if claim_id is None:
            logger.info(f"Skipping message {message_id}: Claim failed (duplicate)")
            return False

        trading_info = extract_trading_info(message_text)
        trading_links = build_dexscreener_links(contract_addresses, message_text)

        # Fetch DexScreener data (with caching via enrichment service)
        dexscreener_data = {}
        for contract_info in trading_links["dexscreener_contracts"]:
            c = contract_info["chain"]
            a = contract_info["address"]
            data = await enrich_token(c, a)
            if data:
                dexscreener_data[f"{c}:{a}"] = data

        # Determine destination
        market_cap = None
        if dexscreener_data:
            first_data = list(dexscreener_data.values())[0]
            market_cap = first_data.get("fdv")

        destination_type = None
        if market_cap is not None:
            if market_cap < get_mc_threshold():
                destination = ctx.destination_entity_under_80k
                destination_type = "under_80k"
            else:
                destination = ctx.destination_entity_80k_or_more
                destination_type = "over_80k"
        else:
            destination = ctx.destination_entity_under_80k
            destination_type = "under_80k"

        dest_label = _entity_label(destination, fallback=str(destination))
        dest_id = getattr(destination, "id", None)

        # Signal intelligence: correlation, scoring, tagging
        multi_caller_count = await record_caller_for_token(address, sender_id) if sender_id else 1

        liquidity = None
        volume_24h = None
        pair_created_at = None
        if dexscreener_data:
            first_data = list(dexscreener_data.values())[0]
            liquidity = first_data.get("liquidity")
            volume_24h = first_data.get("volume_24h")
            pair_created_at = first_data.get("pair_created_at")

        original_timestamp = None
        if message.date:
            original_timestamp = message.date.isoformat()

        confidence_score = compute_signal_confidence(
            sender_id=sender_id,
            market_cap=market_cap,
            liquidity=liquidity,
            chain=chain,
            timestamp=original_timestamp,
            multi_source_count=multi_caller_count,
        )

        signal_tags = compute_tags(
            market_cap=market_cap,
            liquidity=liquidity,
            volume_24h=volume_24h,
            pair_created_at=pair_created_at,
            multi_caller_count=multi_caller_count,
            chain=chain,
        )

        # On-chain safety check
        safety_result = await check_token_safety(chain, address)
        safety_text = safety_summary(safety_result) if safety_result else ""

        caller_badge = get_caller_badge(sender_id) if sender_id else ""
        conf_badge = confidence_badge(confidence_score)
        tags_text = tags_display(signal_tags)

        # Build info message
        message_date = message.date
        timestamp = format_timestamp(message_date, ctx.display_tz) if message_date else "Unknown"

        tokens_with_data = []
        for contract_info in trading_links["dexscreener_contracts"]:
            c = contract_info["chain"]
            a = contract_info["address"]
            key = f"{c}:{a}"
            tokens_with_data.append({
                "type": "contract",
                "chain": c,
                "address": a,
                "link": contract_info["link"],
                "data": dexscreener_data.get(key),
            })

        info_text, primary_dexscreener_link = build_info_message(
            sender_name, sender_id, sender_username, group_name, timestamp,
            tokens_with_data, dexscreener_data, trading_info, contract_addresses,
            message_link, None,
            caller_badge=caller_badge,
            confidence_badge=conf_badge,
            tags_text=tags_text,
            multi_caller_count=multi_caller_count,
            safety_text=safety_text,
        )

        # Forward the message
        forward_success = False
        forwarded_original_ids = []
        copied_ids = []
        info_ids = []

        try:
            for method_name, method_fn in [
                ("forward_messages", lambda: ctx.client.forward_messages(destination, message, from_peer=chat)),
                ("forward_messages(ids)", lambda: ctx.client.forward_messages(destination, [message.id], from_peer=chat)),
                ("forward_to", lambda: message.forward_to(destination)),
                ("forward_messages(auto)", lambda: ctx.client.forward_messages(destination, [message.id])),
            ]:
                try:
                    res = await method_fn()
                    forward_success = True
                    forwarded_original_ids = _message_ids(res)
                    break
                except ChatAdminRequiredError:
                    raise
                except Exception:
                    continue
            if not forward_success:
                raise Exception("All forward methods failed")
        except ChatAdminRequiredError as e:
            logger.error(f"ADMIN PERMISSIONS ERROR: {e}")
            forward_success = False
        except Exception as e:
            logger.error(f"FORWARD FAILED: {e}")
            forward_success = False

        if not forward_success:
            original_text = message.text or message.raw_text or ""
            full_text = info_text + "\n\n" + html.escape(original_text)
            if message.media:
                res = await ctx.client.send_file(
                    destination, message.media, caption=full_text,
                    parse_mode="html", reply_to=None,
                )
                copied_ids = _message_ids(res)
            else:
                res = await ctx.client.send_message(
                    destination, full_text, parse_mode="html", link_preview=False,
                )
                copied_ids = _message_ids(res)
            copy_msg_id = copied_ids[0] if copied_ids else None
            if copy_msg_id is not None:
                chain, address = contract_addresses[0]
                fallback_ds = f"https://dexscreener.com/{DS_CHAINS.get(chain, 'ethereum')}/{address}"
                update_signal_minimal_after_forward(
                    claim_id, copy_msg_id, address, chain,
                    primary_dexscreener_link or fallback_ds,
                    build_message_link(destination, copy_msg_id),
                    destination_type=destination_type,
                )
            else:
                delete_claim(claim_id)
        else:
            info_message = await ctx.client.send_message(
                destination, info_text, parse_mode="html", link_preview=False,
            )
            info_ids = _message_ids(info_message)

            signal_link_url = build_message_link(destination, info_message.id)
            if tokens_with_data and dexscreener_data:
                for token in tokens_with_data:
                    if token["type"] != "contract":
                        continue
                    token_info = {
                        "type": "contract",
                        "chain": token.get("chain", ""),
                        "address": token.get("address", ""),
                        "ticker": "",
                    }
                    update_signal_after_forward(
                        claim_id, info_message.id, token_info, dexscreener_data,
                        primary_dexscreener_link, signal_link_url,
                        destination_type=destination_type,
                    )
                    break
            else:
                chain, address = contract_addresses[0]
                ds_chain = DS_CHAINS.get(chain, "ethereum")
                fallback_ds_link = f"https://dexscreener.com/{ds_chain}/{address}"
                update_signal_minimal_after_forward(
                    claim_id, info_message.id, address, chain,
                    primary_dexscreener_link or fallback_ds_link,
                    signal_link_url,
                    destination_type=destination_type,
                )

        # Emit SignalForwarded event
        fwd_market_cap = None
        if dexscreener_data:
            first_d = list(dexscreener_data.values())[0]
            fwd_market_cap = float(first_d["fdv"]) if first_d.get("fdv") else None
        await emit(SignalForwarded(
            signal_id=claim_id,
            token_address=contract_addresses[0][1],
            chain=contract_addresses[0][0],
            destination_type=destination_type,
            forwarded_message_id=(info_ids[0] if info_ids else (copied_ids[0] if copied_ids else None)),
            market_cap=fwd_market_cap,
        ))

        # Open virtual portfolio position
        entry_price = None
        token_name_for_portfolio = ""
        token_symbol_for_portfolio = ""
        if dexscreener_data:
            first_d = list(dexscreener_data.values())[0]
            entry_price = float(first_d["price"]) if first_d.get("price") else None
            token_name_for_portfolio = first_d.get("token_name", "")
            token_symbol_for_portfolio = first_d.get("token_symbol", "")
        if entry_price and entry_price > 0:
            open_position(
                signal_id=claim_id,
                token_address=contract_addresses[0][1],
                chain=contract_addresses[0][0],
                entry_price=entry_price,
                token_name=token_name_for_portfolio,
                token_symbol=token_symbol_for_portfolio,
                sender_id=sender_id,
                sender_name=sender_name,
            )

        logger.info(
            f"Delivered source msg {message_id} -> {dest_label} (id: {dest_id}) | "
            f"fwd={forwarded_original_ids} info={info_ids} copy={copied_ids}"
        )
        return True
    except Exception as e:
        logger.error(f"Error forwarding message {message_id}: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
