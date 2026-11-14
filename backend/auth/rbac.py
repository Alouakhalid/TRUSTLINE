"""Role-based access control dependencies for the TRUSTLINE Mission API.

RBAC is enforced here at the API boundary and never trusted from the client.
Roles are part of the signed token payload issued at login.
"""
from __future__ import annotations

from typing import Any, Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.security import verify_token

bearer = HTTPBearer(auto_error=False)

ALL_ROLES = ("ASTRONAUT", "MEDICAL_OFFICER", "ADMINISTRATOR")
PRIVILEGED_ROLES = ("MEDICAL_OFFICER", "ADMINISTRATOR")


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict[str, Any]:
    """Resolve the caller from the signed bearer token; 401 when absent or invalid."""
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        return verify_token(credentials.credentials)
    except (ValueError, TypeError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def require_role(*roles: str) -> Callable[..., dict[str, Any]]:
    """Dependency factory enforcing an explicit allow-list of roles (403 otherwise)."""
    allowed = set(roles)

    def dependency(user: dict[str, Any] = Depends(current_user)) -> dict[str, Any]:
        if user.get("role") not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role for this operation")
        return user

    return dependency


require_administrator = require_role("ADMINISTRATOR")
require_privileged = require_role(*PRIVILEGED_ROLES)
