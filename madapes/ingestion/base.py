"""Base ingestor interface for multi-platform signal ingestion."""
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class IngestedSignal:
    """Platform-agnostic signal from any ingestion source."""
    platform: str  # "telegram", "twitter", "discord", "webhook"
    message_text: str
    message_id: str  # platform-specific message ID
    sender_id: str  # platform-specific sender ID
    sender_name: str
    source_name: str  # group/channel/account name
    timestamp: Optional[str] = None
    contract_addresses: List[Tuple[str, str]] = field(default_factory=list)  # [(chain, address), ...]
    metadata: dict = field(default_factory=dict)


class BaseIngestor(ABC):
    """Abstract base class for platform ingestors."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Return the platform name (e.g., 'telegram', 'twitter')."""
        ...

    @abstractmethod
    async def start(self):
        """Start the ingestor (connect, authenticate, begin listening)."""
        ...

    @abstractmethod
    async def stop(self):
        """Stop the ingestor and clean up resources."""
        ...

    async def process_signal(self, signal: IngestedSignal):
        """Process an ingested signal through the unified pipeline.
        Called by subclasses when they detect a contract address.
        """
        from madapes.detection import detect_contract_addresses
        from madapes.services.signal_service import process_signal

        if not signal.contract_addresses:
            signal.contract_addresses = detect_contract_addresses(signal.message_text)

        if not signal.contract_addresses:
            logger.debug(f"[{self.platform_name}] No contracts in message {signal.message_id}")
            return None

        result = process_signal(
            message_text=signal.message_text,
            message_id=int(signal.message_id) if signal.message_id.isdigit() else hash(signal.message_id) % (2**31),
            chat_id=int(signal.sender_id) if signal.sender_id.isdigit() else hash(signal.source_name) % (2**31),
            sender_id=int(signal.sender_id) if signal.sender_id.isdigit() else hash(signal.sender_id) % (2**31),
            sender_name=signal.sender_name,
            group_name=f"{self.platform_name}:{signal.source_name}",
        )
        if result:
            logger.info(
                f"[{self.platform_name}] Signal processed from {signal.source_name}: "
                f"{signal.contract_addresses[0][1][:8]}..."
            )
        return result
