"""MadApes Forwarder - Entry point.
Creates client, resolves entities, registers handlers, starts background tasks.
"""
import asyncio
import logging

import pytz
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError
from telethon.errors.rpcerrorlist import AuthKeyDuplicatedError
from telethon.tl.types import Channel

from config import (
    API_ID, API_HASH, PHONE_NUMBER,
    SOURCE_GROUPS, ALLOWED_SENDER_IDS,
    DESTINATION_UNDER_80K, DESTINATION_80K_OR_MORE, MC_THRESHOLD,
    MAX_SIGNALS, REPORT_DESTINATION, SESSION_NAME, DISPLAY_TIMEZONE,
    DESTINATION_GOLD,
)
from db import init_database, backfill_signal_quality, backfill_missing_intelligence
from madapes.context import app_context
from madapes.handlers import message_handler, edited_message_handler
from madapes.formatting import entity_label as _entity_label
from madapes.http_client import close_session
from madapes.redis_client import get_redis, close_redis
from madapes.reports import background_checker, live_price_monitor
from runner import runner_watcher
from madapes.services.momentum_confirmer import momentum_confirmation_loop

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

try:
    _display_tz = pytz.timezone(DISPLAY_TIMEZONE)
except Exception:
    _display_tz = pytz.timezone("America/New_York")


async def resolve_entity(name, label):
    """Resolve a Telegram entity by name/ID, with logging."""
    logger.info(f"Resolving {label}: '{name}'")
    entity = await client.get_entity(name)
    ename = _entity_label(entity)
    etype = type(entity).__name__
    logger.info(f"{label}: {ename} (type: {etype})")
    return entity


async def _heartbeat_loop(group_count: int):
    """Send periodic heartbeat to API server for bot status tracking."""
    from madapes.http_client import get_session
    while True:
        try:
            session = await get_session()
            async with session.post(
                "http://127.0.0.1:8000/api/internal/heartbeat",
                json={"groups": group_count, "status": "running"},
                timeout=3,
            ) as resp:
                pass
        except Exception:
            pass
        await asyncio.sleep(15)


async def main():
    ctx = app_context
    ctx.client = client
    ctx.display_tz = _display_tz

    init_database(MAX_SIGNALS)

    # Backfill missing data on startup
    backfill_signal_quality()
    backfill_missing_intelligence()

    # Initialize Redis (optional - gracefully degrades if unavailable)
    redis = await get_redis()
    if redis:
        logger.info("Redis connected - caching, events, and rate limiting enabled")
    else:
        logger.info("Redis not available - running without caching/events (local fallback)")

    await client.start()

    if not await client.is_user_authorized():
        logger.info("Not authorized. Starting login...")
        await client.send_code_request(PHONE_NUMBER)
        try:
            code = input("Enter the code you received: ")
            await client.sign_in(PHONE_NUMBER, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)

    logger.info("Client started successfully")

    # Resolve source groups
    verified_groups = []
    for group in SOURCE_GROUPS:
        try:
            entity = await client.get_entity(group)
            group_name = entity.title or entity.username or str(group)
            verified_groups.append(entity)
            if isinstance(entity, Channel) and getattr(entity, "broadcast", False):
                ctx.source_channels.add(entity.id)
                logger.info(f"Watching channel: {group_name} (ID: {entity.id})")
            else:
                logger.info(f"Watching group: {group_name}")
        except Exception as e:
            logger.error(f"Could not find source '{group}': {e}")

    if not verified_groups:
        logger.error("No valid source groups found!")
        return

    # Register handlers
    client.add_event_handler(message_handler, events.NewMessage(chats=verified_groups))
    client.add_event_handler(edited_message_handler, events.MessageEdited(chats=verified_groups))
    logger.info(f"Event handlers registered for {len(verified_groups)} group(s)")

    # Resolve destinations
    try:
        ctx.destination_entity_under_80k = await resolve_entity(DESTINATION_UNDER_80K, f"Destination (MC < ${MC_THRESHOLD:,.0f})")
    except Exception as e:
        logger.error(f"Could not find UNDER_80K destination '{DESTINATION_UNDER_80K}': {e}")
        return

    try:
        ctx.destination_entity_80k_or_more = await resolve_entity(DESTINATION_80K_OR_MORE, f"Destination (MC >= ${MC_THRESHOLD:,.0f})")
    except Exception as e:
        logger.error(f"Could not find 80K_OR_MORE destination '{DESTINATION_80K_OR_MORE}': {e}")
        return

    # Resolve report destination
    if REPORT_DESTINATION:
        try:
            ctx.report_destination_entity = await resolve_entity(REPORT_DESTINATION, "Report destination")
        except Exception as e:
            logger.error(f"Could not resolve REPORT_DESTINATION '{REPORT_DESTINATION}': {e}")
            ctx.report_destination_entity = None
    else:
        logger.error("REPORT_DESTINATION is not set. Reports/updates will not be sent.")

    # Resolve GOLD tier destination (optional — high-conviction signals)
    if DESTINATION_GOLD:
        try:
            ctx.destination_entity_gold = await resolve_entity(DESTINATION_GOLD, "Destination (GOLD tier)")
        except Exception as e:
            logger.error(f"Could not resolve DESTINATION_GOLD '{DESTINATION_GOLD}': {e}")
            ctx.destination_entity_gold = None
    else:
        logger.info("DESTINATION_GOLD not set — GOLD signals will use normal MC-based routing")

    logger.info(f"Bot is running! Watching {len(verified_groups)} group(s). Press Ctrl+C to stop.")

    # Start background tasks
    asyncio.create_task(background_checker())
    asyncio.create_task(runner_watcher(client, ctx.report_destination_entity))
    asyncio.create_task(momentum_confirmation_loop(client, ctx.report_destination_entity))
    asyncio.create_task(live_price_monitor())
    asyncio.create_task(_heartbeat_loop(len(verified_groups)))

    try:
        await client.run_until_disconnected()
    except AuthKeyDuplicatedError as e:
        logger.error(f"AuthKeyDuplicatedError: {e}")
        logger.error("Fix: stop all other running copies, delete the session file, and login again.")
    finally:
        await close_session()
        await close_redis()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
