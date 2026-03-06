"""Contract address and chain detection for MadApes Forwarder."""
import re


def detect_contract_addresses(text):
    """
    Detect cryptocurrency contract addresses across multiple chains.
    Returns the BEST single contract address first, full list for dedup.
    Prioritizes plain-text addresses over URL addresses.
    """
    plain_text_addresses = []
    url_addresses = []

    excluded_words = {
        "pump", "dyor", "risky", "degen", "gamble", "version", "launched",
        "weeks", "creator", "meme", "token", "coin", "swap", "dex",
    }

    url_pattern = r"https?://[^\s]+"
    urls = re.findall(url_pattern, text)
    url_text = " ".join(urls)

    # EVM addresses (0x + 40 hex chars)
    evm_pattern = r"\b0x[a-fA-F0-9]{40}\b"
    for addr in re.findall(evm_pattern, text):
        if addr in url_text:
            url_addresses.append(("ethereum", addr))
        else:
            plain_text_addresses.append(("ethereum", addr))

    # Solana addresses (base58, 32-44 chars)
    solana_pattern = r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b"
    for addr in re.findall(solana_pattern, text):
        if (not addr.startswith("http")
                and "@" not in addr
                and len(addr) >= 32
                and addr.lower() not in excluded_words):
            if addr in url_text:
                url_addresses.append(("solana", addr))
            else:
                plain_text_addresses.append(("solana", addr))

    # Deduplicate
    seen = set()
    unique_plain = []
    for chain, addr in plain_text_addresses:
        if addr not in seen:
            seen.add(addr)
            unique_plain.append((chain, addr))

    seen_url = set()
    unique_url = []
    for chain, addr in url_addresses:
        if addr not in seen_url and addr not in seen:
            seen_url.add(addr)
            unique_url.append((chain, addr))

    all_addresses = list(unique_plain) if unique_plain else list(unique_url)
    if not all_addresses:
        return []

    if unique_plain:
        address_counts = {addr: text.count(addr) for _, addr in unique_plain}

        def sort_key(item):
            _, addr = item
            return (address_counts.get(addr, 0), -unique_plain.index(item))

        sorted_plain = sorted(unique_plain, key=sort_key, reverse=True)
        best = sorted_plain[0]
        others = [(c, a) for c, a in unique_plain if a != best[1]] + unique_url
        return [best] + others
    else:
        return [unique_url[-1]]


def detect_chain_from_context(text, address):
    """Try to detect which chain an address belongs to based on surrounding text."""
    text_lower = text.lower()

    chain_keywords = {
        "bsc": "bsc", "binance": "bsc", "bnb": "bsc",
        "polygon": "polygon", "matic": "polygon",
        "base": "base",
        "arbitrum": "arbitrum", "arb": "arbitrum",
        "optimism": "optimism", "op": "optimism",
        "ethereum": "ethereum", "eth": "ethereum",
        "solana": "solana", "sol": "solana",
    }

    addr_pos = text.lower().find(address.lower())
    if addr_pos == -1:
        return "ethereum"

    context_start = max(0, addr_pos - 50)
    context_end = min(len(text), addr_pos + len(address) + 50)
    context = text_lower[context_start:context_end]

    for keyword, chain in chain_keywords.items():
        if keyword in context:
            return chain

    return "ethereum"


def extract_trading_info(text):
    """Extract trading-related information from message text."""
    info = {
        "price": None,
        "market_cap": None,
        "volume": None,
        "price_change": None,
        "multiplier": None,
    }

    text_lower = text.lower()

    # Extract price
    price_patterns = [
        r"\$(\d+\.?\d*[km]?)\b",
        r"price[:\s]+(\d+\.?\d*[km]?)\b",
        r"@\s*\$?(\d+\.?\d*[km]?)\b",
        r"at\s+\$?(\d+\.?\d*[km]?)\b",
    ]
    for pattern in price_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            for match in matches:
                price_str = match.replace("k", "000").replace("m", "000000")
                try:
                    price_val = float(price_str)
                    if 0.000001 <= price_val <= 1000000:
                        info["price"] = f"${match}"
                        break
                except (ValueError, TypeError):
                    pass
            if info["price"]:
                break

    # Extract market cap
    mc_patterns = [
        r"mc[:\s]+(\d+\.?\d*[kmb]?)\b",
        r"market\s+cap[:\s]+(\d+\.?\d*[kmb]?)\b",
        r"(\d+\.?\d*[kmb]?)\s*mc\b",
    ]
    for pattern in mc_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            info["market_cap"] = matches[0].upper()
            break

    # Extract volume
    volume_patterns = [
        r"volume[:\s]+(\d+\.?\d*[kmb]?)\b",
        r"vol[:\s]+(\d+\.?\d*[kmb]?)\b",
    ]
    for pattern in volume_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            info["volume"] = matches[0].upper()
            break

    # Extract price change
    change_patterns = [
        r"([+-]?\d+\.?\d*)\s*%",
        r"(up|down)\s+(\d+\.?\d*)%?",
    ]
    for pattern in change_patterns:
        matches = re.findall(pattern, text_lower)
        if matches:
            if isinstance(matches[0], tuple):
                direction, value = matches[0]
                sign = "+" if direction == "up" else "-"
                info["price_change"] = f"{sign}{value}%"
            else:
                info["price_change"] = f"{matches[0]}%"
            break

    # Extract multiplier
    multiplier_pattern = r"(\d+\.?\d*)x\b"
    matches = re.findall(multiplier_pattern, text_lower)
    if matches:
        multipliers = [float(m) for m in matches]
        if multipliers:
            max_mult = max(multipliers)
            if max_mult >= 1.0:
                info["multiplier"] = f"{max_mult:.1f}x"

    return info
