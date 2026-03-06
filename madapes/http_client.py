"""Shared aiohttp session for MadApes Forwarder."""
import aiohttp

_session = None


async def get_session():
    global _session
    if _session is None or _session.closed:
        _session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=10),
        )
    return _session


async def close_session():
    global _session
    if _session is not None and not _session.closed:
        await _session.close()
        _session = None
