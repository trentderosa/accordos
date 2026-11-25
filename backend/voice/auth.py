"""Authenticated-or-local gate for voice command POST.

Local loopback clients are allowed without a token.
Non-local clients require ``Authorization: Bearer <ACCORDOS_VOICE_TOKEN>``.
Never executes shell; this module only authorizes the HTTP caller.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, Request

LOCAL_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def voice_token() -> Optional[str]:
    raw = os.environ.get("ACCORDOS_VOICE_TOKEN", "").strip()
    return raw or None


def client_is_local(request: Request) -> bool:
    host = (request.client.host if request.client else "") or ""
    host = host.strip().lower()
    if host in LOCAL_HOSTS:
        return True
    # IPv4-mapped IPv6 loopback
    if host in ("::ffff:127.0.0.1",):
        return True
    return False


def require_voice_access(
    request: Request,
    authorization: Optional[str] = Header(default=None),
) -> dict:
    """FastAPI dependency: allow local OR valid bearer token."""
    if client_is_local(request):
        return {"auth": "local", "local": True}

    token = voice_token()
    if not token:
        raise HTTPException(
            status_code=401,
            detail=(
                "Voice commands from non-local clients require "
                "ACCORDOS_VOICE_TOKEN and Authorization: Bearer …"
            ),
        )

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization: Bearer token for voice command",
        )

    presented = authorization.split(" ", 1)[1].strip()
    if presented != token:
        raise HTTPException(status_code=403, detail="Invalid voice token")

    return {"auth": "bearer", "local": False}
