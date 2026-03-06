"""API authentication - API key based."""
import os
import secrets
from functools import wraps

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# API key from env or auto-generated
_api_key = os.getenv("API_KEY", "").strip()
if not _api_key:
    _api_key = secrets.token_urlsafe(32)
    print(f"[API] Generated API key: {_api_key}")
    print("[API] Set API_KEY in .env to use a fixed key.")


def get_api_key():
    return _api_key


async def verify_api_key(api_key: str = Security(API_KEY_HEADER)):
    """Verify the API key from request header."""
    if not api_key or api_key != _api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return api_key
