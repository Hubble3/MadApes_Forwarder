"""Shared constants for MadApes Forwarder."""

# DexScreener chain identifiers (API path segments)
DS_CHAINS = {
    "ethereum": "ethereum",
    "bsc": "bsc",
    "polygon": "polygon",
    "base": "base",
    "arbitrum": "arbitrum",
    "optimism": "optimism",
    "solana": "solana",
}

# Chain emoji map for display
CHAIN_EMOJI_MAP = {
    "solana": "\U0001f7e3",      # purple circle
    "ethereum": "\U0001f535",    # blue circle
    "bsc": "\U0001f7e1",        # yellow circle
    "polygon": "\U0001f7e3",    # purple circle
    "base": "\U0001f535",       # blue circle
    "arbitrum": "\U0001f535",   # blue circle
    "optimism": "\U0001f534",   # red circle
}

# Chain info: (emoji, short_name) for link building and display
CHAIN_INFO = {
    "ethereum": ("\U0001f537", "ETH"),
    "bsc": ("\U0001f7e1", "BSC"),
    "polygon": ("\U0001f7e3", "MATIC"),
    "base": ("\U0001f535", "BASE"),
    "arbitrum": ("\U0001f534", "ARB"),
    "optimism": ("\U0001f7e0", "OP"),
    "solana": ("\U0001f7e3", "SOL"),
}
