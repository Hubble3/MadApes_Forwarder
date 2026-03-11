"""Shared formatting utilities for MadApes Forwarder."""
import html
from datetime import datetime

from madapes.constants import CHAIN_EMOJI_MAP


def entity_label(entity, fallback="unknown"):
    """Convert a Telegram entity to a readable label (title/username/name)."""
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


def safe_float(v, default=None):
    if v is None:
        return default
    try:
        return float(v)
    except (ValueError, TypeError):
        return default


def format_price(price):
    if price is None:
        return "N/A"
    if price < 0.01:
        return f"${price:.6f}"
    elif price < 1:
        return f"${price:.4f}"
    else:
        return f"${price:.2f}"


def format_currency(value):
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value/1_000_000_000:.2f}B"
    elif value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    elif value >= 1_000:
        return f"${value/1_000:.2f}K"
    else:
        return f"${value:.2f}"


def format_called_time(ts_iso, display_tz=None):
    """Format an ISO timestamp for display. If display_tz given, convert to it."""
    if not ts_iso:
        return "Unknown"
    try:
        import pytz
        dt = datetime.fromisoformat(ts_iso.replace("Z", "+00:00"))
        if display_tz:
            dt = dt.replace(tzinfo=pytz.UTC).astimezone(display_tz) if dt.tzinfo is None else dt.astimezone(display_tz)
        return dt.strftime("%I:%M %p").lstrip("0") or "12:00"
    except Exception:
        return str(ts_iso)


def short_addr(addr, head=8, tail=6):
    if not addr:
        return ""
    if len(addr) <= head + tail + 3:
        return addr
    return f"{addr[:head]}...{addr[-tail:]}"


def token_display_label(token_name, token_symbol):
    """Build display label from token name/symbol, HTML-escaped."""
    if token_name and token_symbol:
        return f"{html.escape(str(token_name))} (${html.escape(str(token_symbol))})"
    elif token_symbol:
        return f"${html.escape(str(token_symbol))}"
    elif token_name:
        return html.escape(str(token_name))
    return "Token"
