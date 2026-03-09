"""Signal service - orchestrates detect -> dedup -> claim -> enrich -> route -> forward."""
import logging
from typing import Optional

from db import (
    claim_signal_if_new,
    delete_claim,
    mark_source_message_processed,
    update_signal_after_forward,
    update_signal_minimal_after_forward,
    was_token_forwarded_recently,
)
from madapes.constants import DS_CHAINS
from madapes.detection import detect_contract_addresses
from madapes.event_bus import emit
from madapes.events import SignalDetected, SignalEnriched, SignalForwarded
from madapes.services.enrichment_service import enrich_token
from utils import utcnow_iso

logger = logging.getLogger(__name__)


async def process_signal(
    message_text: str,
    message_id: int,
    chat_id: Optional[int],
    sender_id: Optional[int],
    sender_name: str,
    group_name: str,
) -> Optional[dict]:
    """Full signal processing pipeline: detect -> dedup -> claim -> enrich.

    Returns a dict with signal processing results, or None if skipped.
    Result dict keys: signal_id, chain, address, contract_addresses,
                      dexscreener_data, market_cap, destination_type.
    """
    # Step 1: Detect contracts
    contract_addresses = detect_contract_addresses(message_text)
    if not contract_addresses:
        return None

    chain, address = contract_addresses[0]

    # Step 2: Recent dedup (channel+discussion double-fire)
    if was_token_forwarded_recently(address, within_seconds=120):
        logger.info(f"Signal dedup: {address[:8]}... forwarded recently")
        return None

    # Step 3: Source message idempotency
    if chat_id is not None and not mark_source_message_processed(chat_id, message_id):
        logger.info(f"Signal dedup: message {message_id} already processed")
        return None

    # Step 4: Claim
    signal_id = claim_signal_if_new(
        address, chain, message_id, group_name, sender_id, sender_name,
        all_addresses=contract_addresses,
    )
    if signal_id is None:
        logger.info(f"Signal dedup: claim failed for {address[:8]}...")
        return None

    # Emit SignalDetected event
    await emit(SignalDetected(
        signal_id=signal_id,
        token_address=address,
        chain=chain,
        sender_id=sender_id,
        sender_name=sender_name,
        source_group=group_name,
        message_id=message_id,
        all_addresses=contract_addresses,
        timestamp=utcnow_iso(),
    ))

    # Step 5: Enrich via DexScreener (with caching)
    dexscreener_data = {}
    data = await enrich_token(chain, address)
    if data:
        dexscreener_data[f"{chain}:{address}"] = data

        # Emit SignalEnriched event
        await emit(SignalEnriched(
            signal_id=signal_id,
            token_address=address,
            chain=chain,
            price=float(data["price"]) if data.get("price") else None,
            market_cap=float(data["fdv"]) if data.get("fdv") else None,
            liquidity=float(data["liquidity"]) if data.get("liquidity") else None,
            volume_24h=float(data["volume_24h"]) if data.get("volume_24h") else None,
            token_name=data.get("token_name", ""),
            token_symbol=data.get("token_symbol", ""),
            dexscreener_link=data.get("pair_url", ""),
        ))

    # Step 6: Determine destination based on market cap
    market_cap = None
    if dexscreener_data:
        first_data = list(dexscreener_data.values())[0]
        market_cap = first_data.get("fdv")

    from madapes.runtime_settings import get_mc_threshold
    if market_cap is not None:
        destination_type = "under_80k" if market_cap < get_mc_threshold() else "over_80k"
    else:
        destination_type = "under_80k"

    return {
        "signal_id": signal_id,
        "chain": chain,
        "address": address,
        "contract_addresses": contract_addresses,
        "dexscreener_data": dexscreener_data,
        "market_cap": market_cap,
        "destination_type": destination_type,
    }


async def finalize_signal_after_forward(
    signal_id: int,
    forwarded_message_id: int,
    token_info: dict,
    dexscreener_data: dict,
    primary_dexscreener_link: Optional[str],
    signal_link: Optional[str],
    destination_type: str,
    token_address: str,
    chain: str,
):
    """Update DB after successful forward and emit SignalForwarded event."""
    if dexscreener_data:
        update_signal_after_forward(
            signal_id, forwarded_message_id, token_info, dexscreener_data,
            primary_dexscreener_link, signal_link,
            destination_type=destination_type,
        )
    else:
        ds_chain = DS_CHAINS.get(chain, "ethereum")
        fallback_ds = f"https://dexscreener.com/{ds_chain}/{token_address}"
        update_signal_minimal_after_forward(
            signal_id, forwarded_message_id, token_address, chain,
            primary_dexscreener_link or fallback_ds, signal_link,
            destination_type=destination_type,
        )

    # Emit event
    market_cap = None
    if dexscreener_data:
        first_data = list(dexscreener_data.values())[0]
        market_cap = float(first_data["fdv"]) if first_data.get("fdv") else None

    await emit(SignalForwarded(
        signal_id=signal_id,
        token_address=token_address,
        chain=chain,
        destination_type=destination_type,
        forwarded_message_id=forwarded_message_id,
        market_cap=market_cap,
    ))


async def cancel_signal(signal_id: int):
    """Cancel a claimed signal that couldn't be forwarded."""
    delete_claim(signal_id)
