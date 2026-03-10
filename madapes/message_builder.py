"""Message building for forwarded signals and info messages."""
import html
import logging
from datetime import datetime, timezone

from madapes.constants import DS_CHAINS, CHAIN_EMOJI_MAP, CHAIN_INFO
from madapes.formatting import format_price, format_currency, short_addr, token_display_label

logger = logging.getLogger(__name__)


def build_message_link(chat, message_id):
    """Build a clickable Telegram link to a message."""
    try:
        if hasattr(chat, "username") and chat.username:
            return f"https://t.me/{chat.username}/{message_id}"
        if hasattr(chat, "id"):
            chat_id = str(chat.id)
            if chat_id.startswith("-100"):
                internal_id = chat_id[4:]
                return f"https://t.me/c/{internal_id}/{message_id}"
    except Exception:
        pass
    return None


def build_dexscreener_links(contract_addresses, message_text=""):
    """Build DexScreener links for contract addresses."""
    from madapes.detection import detect_chain_from_context

    dexscreener_contracts = []

    for chain, address in contract_addresses:
        if chain == "ethereum" and message_text:
            detected_chain = detect_chain_from_context(message_text, address)
            if detected_chain != "ethereum":
                chain = detected_chain

        sa = short_addr(address, head=8, tail=6)
        emoji, chain_name = CHAIN_INFO.get(chain, ("\U0001f537", "ETH"))
        ds_chain = DS_CHAINS.get(chain, "ethereum")
        ds_link = f"https://dexscreener.com/{ds_chain}/{address}"
        dexscreener_contracts.append({
            "link": f'<a href="{ds_link}">\U0001f4ca DexScreener: {emoji} {chain_name} {sa}</a>',
            "chain": chain,
            "address": address,
        })

    return {"dexscreener_contracts": dexscreener_contracts, "dexscreener_tickers": []}


def format_timestamp(message_date, display_tz):
    """Format message timestamp in display timezone."""
    try:
        if message_date.tzinfo is not None:
            local_time = message_date.astimezone(display_tz)
        else:
            utc = message_date.replace(tzinfo=timezone.utc)
            local_time = utc.astimezone(display_tz)
        time_str = local_time.strftime("%I:%M %p").lstrip("0")
        from datetime import datetime as dt
        now = dt.now(display_tz)
        if local_time.date() != now.date():
            return f"{local_time.strftime('%b %d')}, {time_str}"
        return time_str
    except Exception:
        return "Unknown"


def build_info_message(
    sender_name, sender_id, sender_username, group_name, timestamp,
    tokens_with_data, dexscreener_data, trading_info, contract_addresses,
    message_link, primary_dexscreener_link,
    caller_badge="", confidence_badge="", strategy_badge="", tags_text="", multi_caller_count=1,
    safety_text="",
):
    """Build the organized info message for a forwarded signal.
    Returns (info_text, primary_dexscreener_link).
    """
    info_sections = []
    info_sections.append("\u2501" * 32)
    info_sections.append("\U0001f4ca <b>TRADING ALERT</b>")
    info_sections.append("")

    # Sender info
    sender_link_text = html.escape(sender_name)
    if sender_id:
        sender_link_text = f'<a href="tg://user?id={sender_id}">{sender_link_text}</a>'
    sender_part = f"\U0001f464 {sender_link_text}"
    if caller_badge:
        sender_part += f" {caller_badge}"
    if sender_username:
        sender_part += f" @{html.escape(sender_username)}"
    info_sections.append(f"{sender_part} | \U0001f4cd {html.escape(group_name)} | \U0001f550 <code>{timestamp}</code>")

    # Intelligence line: strategy tier + confidence + tags + multi-caller
    intel_parts = []
    if strategy_badge:
        intel_parts.append(strategy_badge)
    if confidence_badge:
        intel_parts.append(f"\U0001f3af {confidence_badge}")
    if multi_caller_count >= 2:
        intel_parts.append(f"\U0001f525 MULTI-CALLER ({multi_caller_count}x)")
    if tags_text:
        intel_parts.append(tags_text)
    if intel_parts:
        info_sections.append(" | ".join(intel_parts))
    if safety_text:
        info_sections.append(f"\U0001f6e1\ufe0f {safety_text}")

    info_sections.append("")

    if tokens_with_data:
        token = tokens_with_data[0]
        data = token.get("data") or {}
        display_chain = (data.get("chain") or token["chain"] or "ethereum").lower()
        token["chain"] = display_chain
        chain_emoji = CHAIN_EMOJI_MAP.get(display_chain, "\U0001f48e")

        token_name = data.get("token_name", "")
        token_symbol = data.get("token_symbol", "")
        label = token_display_label(token_name, token_symbol) if (token_name or token_symbol) else f"{chain_emoji} {display_chain.upper()}"
        info_sections.append(f"\U0001f4ca Token: {label}")
        info_sections.append(f"\U0001f517 Address: <code>{html.escape(token['address'])}</code>")
        info_sections.append("")
        info_sections.append(f"{chain_emoji} {display_chain.upper()}")

        if data:
            stats_parts = []
            if data.get("price") is not None:
                price = float(data["price"])
                stats_parts.append(f"\U0001f4b5 Price: {format_price(price)}")
            if data.get("price_change_24h") is not None:
                change = float(data["price_change_24h"])
                change_emoji = "\U0001f7e2" if change >= 0 else "\U0001f534"
                stats_parts.append(f"{change_emoji} 24h: {change:+.2f}%")
            if data.get("liquidity") is not None:
                liq = float(data["liquidity"])
                stats_parts.append(f"\U0001f4a7 Liq: {format_currency(liq)}")
            if data.get("fdv") is not None:
                fdv = float(data["fdv"])
                stats_parts.append(f"\U0001f4ca MC: {format_currency(fdv)}")
            if stats_parts:
                info_sections.append(" | ".join(stats_parts))

            vol_line_parts = []
            if data.get("volume_1h") is not None:
                vol_line_parts.append(f"1h {format_currency(float(data['volume_1h']))}")
            if data.get("volume_24h") is not None:
                vol_line_parts.append(f"24h {format_currency(float(data['volume_24h']))}")
            dex_part = None
            if data.get("exchange"):
                exchange_display = data["exchange"].replace("_", " ").title()
                if exchange_display:
                    dex_part = f"\U0001f3db\ufe0f DEX: {exchange_display}"
            second_line = []
            if vol_line_parts:
                second_line.append(f"\U0001f4b9 Volume: {' | '.join(vol_line_parts)}")
            if dex_part:
                second_line.append(dex_part)
            if second_line:
                info_sections.append(" | ".join(second_line))

        # DexScreener link
        ds_chain = DS_CHAINS.get(display_chain, "ethereum")
        pair_url = data.get("pair_url") if data else None
        pair_address = data.get("pair_address") if data else None
        addr = token["address"]
        if pair_url and isinstance(pair_url, str) and pair_url.startswith("https://"):
            primary_dexscreener_link = pair_url.strip()
        elif pair_address:
            primary_dexscreener_link = f"https://dexscreener.com/{ds_chain}/{pair_address}"
        else:
            primary_dexscreener_link = f"https://dexscreener.com/{ds_chain}/{addr}"
    else:
        if trading_info.get("price") or trading_info.get("market_cap") or trading_info.get("volume"):
            data_parts = []
            if trading_info.get("price"):
                data_parts.append(f"\U0001f4b0 {trading_info['price']}")
            if trading_info.get("market_cap"):
                data_parts.append(f"\U0001f48e MC: ${trading_info['market_cap']}")
            if trading_info.get("volume"):
                data_parts.append(f"\U0001f4b9 Vol: ${trading_info['volume']}")
            if trading_info.get("price_change"):
                change = trading_info["price_change"]
                emoji = "\U0001f7e2" if change.startswith("+") else "\U0001f534" if change.startswith("-") else "\u26aa"
                data_parts.append(f"{emoji} {change}")
            if data_parts:
                info_sections.append("\U0001f4ca " + " | ".join(data_parts))

    # Links
    links_parts = []
    if primary_dexscreener_link:
        links_parts.append(f'\U0001f4ca <a href="{primary_dexscreener_link}">DexScreener</a>')
    if contract_addresses:
        chain, address = contract_addresses[0]
        if (chain or "").lower() == "solana" and address:
            photon_link = f"https://photon-sol.tinyastro.io/en/lp/{address}"
            links_parts.append(f'\u26a1 <a href="{html.escape(photon_link)}">Photon</a>')
    if message_link:
        links_parts.append(f'\U0001f517 <a href="{message_link}">Original Message</a>')
    if links_parts:
        info_sections.append("")
        info_sections.append(" | ".join(links_parts))

    info_sections.append("\u2501" * 32)
    return "\n".join(info_sections), primary_dexscreener_link


def resolve_report_links(row, addr, chain, dest_under_80k, dest_over_80k):
    """Resolve DexScreener and signal Telegram links for reports.
    Returns (ds_link, sig_link).
    """
    ds_link = row["original_dexscreener_link"]
    sig_link = row["signal_link"]
    token_type = row["token_type"]

    ds_str = str(ds_link) if ds_link is not None else ""
    sig_str = str(sig_link) if sig_link is not None else ""

    # Fix swapped links
    if ds_str and "t.me" in ds_str and sig_str and "dexscreener" in sig_str:
        ds_link, sig_link = sig_link, ds_link
        ds_str, sig_str = sig_str, ds_str
    if sig_str and "dexscreener" in sig_str.lower():
        sig_link = None
        sig_str = ""
    if ds_str and "t.me" in ds_str:
        ds_link = None
        ds_str = ""

    # Fallback DexScreener
    if not ds_link and addr and chain and (token_type == "contract" or addr):
        chain_key = (chain or "").lower() if isinstance(chain, str) else "solana"
        ds_link = f"https://dexscreener.com/{DS_CHAINS.get(chain_key, 'solana')}/{addr}"

    # Build sig_link from destination if missing
    if not sig_str or "dexscreener" in sig_str.lower():
        fwd_msg_id = row["forwarded_message_id"]
        dest_type = row["destination_type"]
        if fwd_msg_id and dest_type:
            dest = None
            if dest_type == "under_80k":
                dest = dest_under_80k
            elif dest_type == "over_80k":
                dest = dest_over_80k
            if dest:
                sig_link = build_message_link(dest, fwd_msg_id)

    def _valid_link(v, must_contain):
        if v is None:
            return None
        s = str(v) if not isinstance(v, str) else v
        return s if must_contain in s else None

    return (_valid_link(ds_link, "http"), _valid_link(sig_link, "t.me"))
