"""Shared utilities for MadApes Forwarder."""
from datetime import datetime, timezone


def utcnow_naive():
    """UTC now as naive datetime (keeps DB timestamps consistent)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utcnow_iso():
    return utcnow_naive().isoformat()
