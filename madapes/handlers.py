"""Telegram event handlers for MadApes Forwarder."""
import logging

from telethon.tl.types import Channel

from config import ALLOWED_SENDER_IDS
from madapes.context import app_context
from madapes.detection import detect_contract_addresses
from madapes.forwarding import forward_message
from utils import utcnow_naive

logger = logging.getLogger(__name__)


async def message_handler(event):
    """Handle new messages from any source group."""
    try:
        ctx = app_context
        message = event.message
        message_id = message.id
        sender_id = message.sender_id

        try:
            chat = await event.get_chat()
            sender = await event.get_sender()
            group_name = chat.title or chat.username or "Unknown"
        except Exception as e:
            logger.error(f"Error getting chat/sender info for message {message_id}: {e}")
            return

        is_channel_source = (
            isinstance(chat, Channel)
            and chat.id in ctx.source_channels
            and getattr(chat, "broadcast", False)
        )

        should_forward = is_channel_source or sender_id in ALLOWED_SENDER_IDS
        if not should_forward:
            return

        try:
            forwarded = await forward_message(message, chat, sender)
            if forwarded:
                logger.info(f"Forwarded message {message_id}")
        except Exception as forward_error:
            logger.error(f"Failed to forward message {message_id}: {forward_error}")
    except Exception as e:
        logger.error(f"Error in message_handler: {e}")
        import traceback
        logger.error(traceback.format_exc())


async def edited_message_handler(event):
    """Handle edited messages to catch quick 'added contract' edits."""
    try:
        ctx = app_context
        message = event.message
        if not message:
            return

        message_id = message.id
        sender_id = message.sender_id

        try:
            chat = await event.get_chat()
            sender = await event.get_sender()
            group_name = chat.title or chat.username or "Unknown"
        except Exception:
            return

        ctx.prune_pending()
        k = ctx.pending_key(chat, message_id)
        pending_ts = ctx.pending_no_contract.get(k) if k else None

        should_check = pending_ts is not None
        if not should_check:
            try:
                msg_dt = message.date
                if msg_dt is None:
                    return
                msg_dt_naive = msg_dt.replace(tzinfo=None) if getattr(msg_dt, "tzinfo", None) else msg_dt
                age_sec = (utcnow_naive() - msg_dt_naive).total_seconds()
                if age_sec <= ctx.pending_edit_ttl:
                    should_check = True
            except Exception:
                return

        if not should_check:
            return

        is_channel_source = (
            isinstance(chat, Channel)
            and chat.id in ctx.source_channels
            and getattr(chat, "broadcast", False)
        )
        if not (is_channel_source or sender_id in ALLOWED_SENDER_IDS):
            return

        message_text = message.text or message.raw_text or ""
        if not detect_contract_addresses(message_text):
            return

        logger.info(f"Edited message {message_id} in {group_name}: contract detected, re-processing")
        forwarded = await forward_message(message, chat, sender)
        if k:
            ctx.pending_no_contract.pop(k, None)
        if forwarded:
            logger.info(f"Edited message {message_id}: forwarded after contract was added")
    except Exception as e:
        logger.error(f"Error in edited_message_handler: {e}")
        import traceback
        logger.error(traceback.format_exc())
