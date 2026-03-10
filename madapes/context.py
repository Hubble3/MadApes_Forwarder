"""Application context replacing global mutable state."""
from dataclasses import dataclass, field
from typing import Any, Optional, Set, Dict, Tuple
import time


@dataclass
class AppContext:
    """Holds all mutable application state, replacing scattered globals."""
    client: Any = None
    destination_entity_under_80k: Any = None
    destination_entity_80k_or_more: Any = None
    destination_entity_gold: Any = None
    report_destination_entity: Any = None
    source_channels: Set[int] = field(default_factory=set)
    display_tz: Any = None
    last_new_day_date: Any = None
    last_daily_report_date: Any = None

    # Pending edit cache: (chat_id, message_id) -> first_seen_unix_seconds
    pending_no_contract: Dict[Tuple[int, int], float] = field(default_factory=dict)
    pending_edit_ttl: int = 30

    def prune_pending(self, now=None):
        now = now if now is not None else time.time()
        cutoff = now - self.pending_edit_ttl
        for key, ts in list(self.pending_no_contract.items()):
            if ts < cutoff:
                self.pending_no_contract.pop(key, None)

    def pending_key(self, chat, message_id):
        chat_id = getattr(chat, "id", None)
        if chat_id is None or message_id is None:
            return None
        return (chat_id, message_id)

    def require_report_destination(self):
        if self.report_destination_entity is None:
            raise RuntimeError("REPORT_DESTINATION is not resolved.")
        return self.report_destination_entity


# Singleton instance
app_context = AppContext()
