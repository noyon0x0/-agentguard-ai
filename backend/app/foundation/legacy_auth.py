"""Shared bearer authentication for retained legacy demo API routes."""

from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

legacy_bearer = HTTPBearer(auto_error=False)


def require_legacy_admin(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(legacy_bearer),
) -> str:
    """Require an explicitly configured operator token on legacy API routes."""
    expected = getattr(request.app.state, "admin_token", "")
    if not expected:
        raise HTTPException(status_code=503, detail={"code": "ADMIN_AUTH_NOT_CONFIGURED"})
    supplied = credentials.credentials if credentials and credentials.scheme.casefold() == "bearer" else ""
    if not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail={"code": "UNAUTHORIZED"})
    return "admin"
