"""Discord ingestor - monitors specified Discord channels for token signals."""
import asyncio
import logging
import os
from typing import Optional

from madapes.detection import detect_contract_addresses
from madapes.ingestion.base import BaseIngestor, IngestedSignal

logger = logging.getLogger(__name__)


class DiscordIngestor(BaseIngestor):
    """Discord ingestor using discord.py.

    Monitors specified channels for messages containing contract addresses.
    Requires DISCORD_BOT_TOKEN, DISCORD_CHANNELS in .env.
    """

    def __init__(self):
        self._bot = None
        self._task: Optional[asyncio.Task] = None
        self._channels: list = []

    @property
    def platform_name(self) -> str:
        return "discord"

    async def start(self):
        """Start the Discord bot."""
        token = os.getenv("DISCORD_BOT_TOKEN", "").strip()
        if not token:
            logger.warning("Discord ingestor: DISCORD_BOT_TOKEN not set - disabled")
            return

        channels_str = os.getenv("DISCORD_CHANNELS", "").strip()
        if channels_str:
            self._channels = [c.strip() for c in channels_str.split(",") if c.strip()]

        try:
            import discord

            intents = discord.Intents.default()
            intents.message_content = True
            self._bot = discord.Client(intents=intents)

            ingestor = self  # closure ref

            @self._bot.event
            async def on_ready():
                logger.info(f"Discord ingestor connected as {self._bot.user}")
                if self._channels:
                    logger.info(f"Watching channels: {self._channels}")
                else:
                    logger.info("Watching all channels (no filter set)")

            @self._bot.event
            async def on_message(message):
                # Ignore bot's own messages
                if message.author == self._bot.user:
                    return

                # Filter by channel if configured
                if self._channels:
                    channel_name = getattr(message.channel, "name", "")
                    channel_id = str(message.channel.id)
                    if channel_name not in self._channels and channel_id not in self._channels:
                        return

                text = message.content or ""
                contracts = detect_contract_addresses(text)
                if not contracts:
                    return

                guild_name = getattr(message.guild, "name", "DM") if message.guild else "DM"
                channel_name = getattr(message.channel, "name", "unknown")

                signal = IngestedSignal(
                    platform="discord",
                    message_text=text,
                    message_id=str(message.id),
                    sender_id=str(message.author.id),
                    sender_name=str(message.author),
                    source_name=f"discord:{guild_name}#{channel_name}",
                    timestamp=message.created_at.isoformat() if message.created_at else None,
                    contract_addresses=contracts,
                    metadata={
                        "guild_id": str(message.guild.id) if message.guild else None,
                        "channel_id": str(message.channel.id),
                    },
                )
                await ingestor.process_signal(signal)

            self._task = asyncio.create_task(self._bot.start(token))
            logger.info("Discord ingestor starting...")

        except ImportError:
            logger.warning("Discord ingestor: discord.py not installed - disabled")

    async def stop(self):
        """Stop the Discord bot."""
        if self._bot:
            await self._bot.close()
        if self._task and not self._task.done():
            self._task.cancel()
        logger.info("Discord ingestor stopped")
