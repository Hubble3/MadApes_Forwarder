"""Webhook endpoint for external signal sources."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Tuple

from api.auth import verify_api_key
from madapes.detection import detect_contract_addresses
from madapes.ingestion.base import IngestedSignal

router = APIRouter()


class WebhookSignal(BaseModel):
    """Webhook payload for submitting a signal."""
    text: str
    sender_name: str = "webhook"
    source: str = "webhook"
    platform: str = "webhook"
    sender_id: Optional[str] = None
    timestamp: Optional[str] = None


@router.post("/signal")
async def receive_signal(payload: WebhookSignal, api_key: str = Depends(verify_api_key)):
    """Receive a signal from an external source via webhook."""
    contracts = detect_contract_addresses(payload.text)
    if not contracts:
        raise HTTPException(status_code=400, detail="No contract addresses detected in text")

    signal = IngestedSignal(
        platform=payload.platform,
        message_text=payload.text,
        message_id=str(hash(payload.text) % (2**31)),
        sender_id=payload.sender_id or str(hash(payload.sender_name) % (2**31)),
        sender_name=payload.sender_name,
        source_name=payload.source,
        timestamp=payload.timestamp,
        contract_addresses=contracts,
    )

    # Process through the signal pipeline
    from madapes.services.signal_service import process_signal

    result = process_signal(
        message_text=signal.message_text,
        message_id=int(signal.message_id),
        chat_id=hash(signal.source_name) % (2**31),
        sender_id=int(signal.sender_id) if signal.sender_id.isdigit() else hash(signal.sender_id) % (2**31),
        sender_name=signal.sender_name,
        group_name=f"{signal.platform}:{signal.source_name}",
    )

    return {
        "status": "accepted",
        "contracts_found": len(contracts),
        "contracts": [{"chain": c, "address": a} for c, a in contracts],
        "signal_id": result.get("signal_id") if result else None,
    }
