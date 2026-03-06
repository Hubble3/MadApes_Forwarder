"""Signal tagging service - auto-tags signals based on characteristics."""
import logging
from typing import List, Optional

logger = logging.getLogger(__name__)

# Market cap tiers
MC_MICRO = 50_000        # < $50K
MC_LOW = 500_000         # $50K - $500K
MC_MID = 5_000_000       # $500K - $5M
# > $5M = high_cap

# Volume threshold for "high volume" tag
HIGH_VOLUME_24H = 500_000  # $500K

# Pair age threshold for "new pair" tag (seconds)
NEW_PAIR_MAX_AGE = 86400  # 24 hours


def compute_tags(
    market_cap: Optional[float] = None,
    liquidity: Optional[float] = None,
    volume_24h: Optional[float] = None,
    pair_created_at: Optional[str] = None,
    multi_caller_count: int = 1,
    chain: Optional[str] = None,
) -> List[str]:
    """Compute auto-tags for a signal based on its characteristics.

    Returns a list of tag strings.
    """
    tags = []

    # Market cap tier
    if market_cap is not None and market_cap > 0:
        if market_cap < MC_MICRO:
            tags.append("micro_cap")
        elif market_cap < MC_LOW:
            tags.append("low_cap")
        elif market_cap < MC_MID:
            tags.append("mid_cap")
        else:
            tags.append("high_cap")

    # High volume
    if volume_24h is not None and volume_24h >= HIGH_VOLUME_24H:
        tags.append("high_volume")

    # New pair detection
    if pair_created_at:
        try:
            from datetime import datetime
            from utils import utcnow_naive
            created = datetime.fromisoformat(pair_created_at.replace("Z", "+00:00"))
            age_seconds = (utcnow_naive() - created.replace(tzinfo=None)).total_seconds()
            if 0 < age_seconds < NEW_PAIR_MAX_AGE:
                tags.append("new_pair")
        except Exception:
            pass

    # Multi-caller
    if multi_caller_count >= 2:
        tags.append("multi_caller")

    # Low liquidity warning
    if liquidity is not None and 0 < liquidity < 5000:
        tags.append("low_liq")

    return tags


def tags_display(tags: List[str]) -> str:
    """Format tags for display in messages."""
    if not tags:
        return ""
    formatted = " ".join(f"#{t}" for t in tags)
    return f"<i>{formatted}</i>"
