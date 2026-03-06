"""Telegram ingestor - wraps existing Telegram handlers into the ingestor pattern."""
import logging
from typing import Optional

from madapes.ingestion.base import BaseIngestor, IngestedSignal

logger = logging.getLogger(__name__)


class TelegramIngestor(BaseIngestor):
    """Telegram ingestor using existing Telethon client and handlers.

    This wraps the existing message_handler/edited_message_handler
    into the unified ingestor pattern. The actual Telegram client
    setup remains in main.py - this class provides the interface.
    """

    @property
    def platform_name(self) -> str:
        return "telegram"

    async def start(self):
        """Telegram client is started in main.py - this is a no-op."""
        logger.info("Telegram ingestor: using existing client from main.py")

    async def stop(self):
        """Telegram client is stopped in main.py - this is a no-op."""
        pass

    def message_to_signal(self, message, chat, sender) -> Optional[IngestedSignal]:
        """Convert a Telethon message to an IngestedSignal."""
        from madapes.detection import detect_contract_addresses
        from telethon.tl.types import Channel

        message_text = message.text or message.raw_text or ""
        sender_id = str(message.sender_id or 0)
        sender_name = "Unknown"

        if sender:
            if isinstance(sender, Channel):
                sender_name = getattr(sender, "title", None) or "Channel"
            elif hasattr(sender, "first_name"):
                sender_name = f"{sender.first_name or ''} {sender.last_name or ''}".strip() or "Unknown"

        group_name = getattr(chat, "title", None) or getattr(chat, "username", None) or "Unknown"
        contracts = detect_contract_addresses(message_text)

        return IngestedSignal(
            platform="telegram",
            message_text=message_text,
            message_id=str(message.id),
            sender_id=sender_id,
            sender_name=sender_name,
            source_name=group_name,
            timestamp=message.date.isoformat() if message.date else None,
            contract_addresses=contracts,
            metadata={
                "chat_id": getattr(chat, "id", None),
                "has_media": bool(message.media),
            },
        )
