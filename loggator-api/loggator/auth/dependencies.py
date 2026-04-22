"""
FastAPI dependencies for authentication.

Current behavior: require_auth returns None (no enforcement).
Once IAM is integrated, it will validate the Bearer token and
return the UserClaims, raising HTTP 401 if invalid.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from loggator.auth.schemas import UserClaims
from loggator.auth.client import IAMClient

# Shared IAM client instance (will be initialized with config in future)
_iam_client = IAMClient()

# HTTP Bearer scheme for OpenAPI docs (marks endpoints as requiring auth)
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
) -> Optional[UserClaims]:
    """
    FastAPI dependency that validates the request's Bearer token.

    Current behavior: returns None (all requests pass through).

    Future behavior: extracts Bearer token from Authorization header,
    calls IAMClient.verify_token(), raises HTTP 401 if invalid.

    Usage:
        @router.get("/protected")
        async def protected_route(user: UserClaims = Depends(require_auth)):
            ...
    """
    # TODO: uncomment once IAM integration is implemented:
    # if credentials is None:
    #     raise HTTPException(status_code=401, detail="Authentication required")
    # user = await _iam_client.verify_token(credentials.credentials)
    # if user is None:
    #     raise HTTPException(status_code=401, detail="Invalid or expired token")
    # return user

    return None  # No-op: all requests allowed
