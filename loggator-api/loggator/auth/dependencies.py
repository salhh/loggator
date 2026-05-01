"""
FastAPI dependencies for authentication.

Current behavior: require_auth returns None (no enforcement).
Once IAM is integrated, it will validate the Bearer token and
return the UserClaims, raising HTTP 401 if invalid.
"""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select

from loggator.auth.schemas import UserClaims
from loggator.auth.client import IAMClient
from loggator.config import settings
from loggator.db.models import Membership, Tenant
from loggator.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

# Shared IAM client instance (will be initialized with config in future)
_iam_client = IAMClient()

# HTTP Bearer scheme for OpenAPI docs (marks endpoints as requiring auth)
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
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
    if settings.auth_disabled:
        return None

    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = await _iam_client.verify_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Make claims available to middleware (audit log actor fields).
    request.state.user_claims = user
    return user


async def require_current_tenant(
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> UUID:
    """
    Resolve tenant context from JWT claims + optional X-Tenant-Id header.

    Rules:
    - If AUTH is disabled: fall back to existing tenancy dependency via default tenant.
    - If token has tenant_id: use it (single-tenant token).
    - If token has tenant_ids: require X-Tenant-Id to select the active tenant.
    - platform_admin may access any active tenant when X-Tenant-Id is provided.
    - Non-platform users must have an explicit membership for the chosen tenant.
    """
    from loggator.tenancy.bootstrap import get_default_tenant_id

    if settings.auth_disabled or user is None:
        return await get_default_tenant_id(session)

    # Choose tenant
    chosen: UUID | None = None
    if user.tenant_id:
        chosen = user.tenant_id
    elif x_tenant_id:
        try:
            chosen = UUID(x_tenant_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header")
    else:
        raise HTTPException(status_code=400, detail="X-Tenant-Id header required for multi-tenant tokens")

    tenant = await session.get(Tenant, chosen)
    if tenant is None or tenant.status != "active":
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")

    is_platform_admin = "platform_admin" in (user.platform_roles or [])
    if not is_platform_admin:
        result = await session.execute(
            select(Membership).where(
                Membership.user_id == user.user_id,
                Membership.tenant_id == chosen,
            ).limit(1)
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=403, detail="Not a member of this tenant")

    request.state.tenant_id = chosen
    return chosen


def require_platform_admin(user: Annotated[Optional[UserClaims], Depends(require_auth)]) -> UserClaims:
    if settings.auth_disabled and user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user is None or "platform_admin" not in (user.platform_roles or []):
        raise HTTPException(status_code=403, detail="platform_admin required")
    return user


def require_tenant_admin(user: Annotated[Optional[UserClaims], Depends(require_auth)]) -> UserClaims:
    if settings.auth_disabled and user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if user is None or "tenant_admin" not in (user.roles or []):
        raise HTTPException(status_code=403, detail="tenant_admin required")
    return user
