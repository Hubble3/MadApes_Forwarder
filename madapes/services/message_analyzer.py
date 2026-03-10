"""
Message quality analysis module.

Analyzes raw Telegram signal message text to extract quality indicators
that predict whether a signal is high-quality (likely runner) or
low-quality (likely spam/rug).
"""

import re
import logging

logger = logging.getLogger(__name__)

# --- Link patterns ---
SOCIAL_LINK_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/[^\s]+", re.IGNORECASE
)
DEXSCREENER_LINK_RE = re.compile(
    r"https?://(?:www\.)?dexscreener\.com/[^\s]+", re.IGNORECASE
)
COMMUNITY_LINK_RE = re.compile(
    r"https?://(?:www\.)?(?:t\.me|discord\.gg)/[^\s]+", re.IGNORECASE
)
URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)

# --- Narrative keywords ---
PRIMARY_PHRASES = [
    "team pushing",
    "team building",
    "good narrative",
    "strong narrative",
    "good dev",
    "based dev",
    "community growing",
    "organic growth",
    "real utility",
    "partnership",
]

SECONDARY_KEYWORDS = [
    "team",
    "community",
    "narrative",
    "utility",
    "dev",
    "pushing",
    "building",
    "launched",
    "airdrop",
    "partnership",
    "ecosystem",
    "trending",
]

NEGATIVE_KEYWORDS = [
    "rug",
    "scam",
    "honeypot",
    "fake",
    "copy",
    "clone",
]

# Pre-compile word-boundary patterns for secondary and negative keywords
_SECONDARY_RES = [
    re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in SECONDARY_KEYWORDS
]
_NEGATIVE_RES = [
    re.compile(rf"\b{re.escape(kw)}\b", re.IGNORECASE) for kw in NEGATIVE_KEYWORDS
]


def analyze_message(text: str) -> dict:
    """Analyze a signal message for quality indicators.

    Returns a dict with quality metrics including a composite score (0-15)
    and a label of 'high', 'medium', or 'low'.
    """
    if not text:
        return {
            "has_social_links": False,
            "social_links": [],
            "has_dexscreener_link": False,
            "has_narrative": False,
            "narrative_keywords": [],
            "has_analysis": False,
            "message_length": 0,
            "has_community_link": False,
            "has_chart_image": False,
            "quality_score": 0.0,
            "quality_label": "low",
        }

    # --- Social links ---
    social_links = SOCIAL_LINK_RE.findall(text)
    has_social_links = len(social_links) > 0

    # --- DexScreener link ---
    has_dexscreener_link = bool(DEXSCREENER_LINK_RE.search(text))

    # --- Community links ---
    has_community_link = bool(COMMUNITY_LINK_RE.search(text))

    # --- Chart mention ---
    has_chart_image = bool(re.search(r"\bchart\b", text, re.IGNORECASE))

    # --- Content text (URLs stripped) for analysis depth ---
    content_text = URL_RE.sub("", text).strip()
    message_length = len(text)
    has_analysis = len(content_text) > 100
    is_minimal = len(content_text) < 20

    # --- Narrative keyword matching ---
    text_lower = text.lower()
    matched_keywords: list[str] = []

    # Primary phrases (substring match, case-insensitive)
    matched_primary: list[str] = []
    for phrase in PRIMARY_PHRASES:
        if phrase in text_lower:
            matched_primary.append(phrase)

    # Secondary keywords (word-boundary match)
    matched_secondary: list[str] = []
    for kw, pattern in zip(SECONDARY_KEYWORDS, _SECONDARY_RES):
        if pattern.search(text):
            matched_secondary.append(kw)

    # Negative keywords (word-boundary match)
    matched_negative: list[str] = []
    for kw, pattern in zip(NEGATIVE_KEYWORDS, _NEGATIVE_RES):
        if pattern.search(text):
            matched_negative.append(kw)

    matched_keywords = matched_primary + matched_secondary
    has_narrative = len(matched_keywords) > 0

    # --- Quality score computation (0-15) ---
    score = 0.0

    # Social links: +4pts
    if has_social_links:
        score += 4.0

    # Narrative: primary +1.5 each (max 6), secondary +1 each (max 5), total narrative max 6
    narrative_score = 0.0
    narrative_score += min(len(matched_primary) * 1.5, 6.0)
    narrative_score += min(len(matched_secondary) * 1.0, 5.0)
    narrative_score = min(narrative_score, 6.0)
    score += narrative_score

    # Negative keywords: -2pts each
    score -= len(matched_negative) * 2.0

    # DexScreener chart: +2pts
    if has_dexscreener_link:
        score += 2.0

    # Community link: +1pt
    if has_community_link:
        score += 1.0

    # Analysis depth > 100 chars: +2pts
    if has_analysis:
        score += 2.0

    # Minimal message < 20 chars content: -3pts
    if is_minimal:
        score -= 3.0

    # Cap at [0, 15]
    score = max(0.0, min(score, 15.0))

    # --- Quality label ---
    if score >= 10:
        quality_label = "high"
    elif score >= 5:
        quality_label = "medium"
    else:
        quality_label = "low"

    result = {
        "has_social_links": has_social_links,
        "social_links": social_links,
        "has_dexscreener_link": has_dexscreener_link,
        "has_narrative": has_narrative,
        "narrative_keywords": matched_keywords,
        "has_analysis": has_analysis,
        "message_length": message_length,
        "has_community_link": has_community_link,
        "has_chart_image": has_chart_image,
        "quality_score": score,
        "quality_label": quality_label,
    }

    logger.debug(
        "Message analysis: score=%.1f label=%s keywords=%s",
        score,
        quality_label,
        matched_keywords,
    )

    return result
