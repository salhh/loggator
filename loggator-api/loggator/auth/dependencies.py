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
from loggator.auth.schemas import UserClaims
from loggator.auth.client import IAMClient
from loggator.config import settings
from loggator.db.session import get_session
from sqlalchemy.ext.asyncio import AsyncSession

# Shared IAM client instance (will be initialized with config in future)
_iam_client = IAMClient()

# HTTP Bearer scheme for OpenAPI docs (marks endpoints as requiring auth)
_bearer_scheme = HTTPBearer(auto_error=False)


async def require_auth(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
    session: AsyncSession = Depends(get_session),
) -> Optional[UserClaims]:
    """
    FastAPI dependency that validates the request's Bearer token.

    When auth is enabled, verifies the Bearer token and auto-provisions
    a User row (and optionally a default-tenant Membership) on first login.
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

    # Auto-provision User row on first OIDC login.
    from loggator.tenancy.membership import ensure_default_membership, get_or_create_user

    db_user, created = await get_or_create_user(session, user.user_id, user.email)
    if created and settings.auto_provision_default_tenant:
        await ensure_default_membership(session, db_user)
    await session.commit()

    return user


async def require_current_tenant(
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> UUID:
    """Same rules as ``get_effective_tenant_id`` (alias for clearer call sites)."""
    from loggator.tenancy.deps import resolve_tenant_for_principal

    return await resolve_tenant_for_principal(session, request, user, x_tenant_id)


def require_platform_admin(user: Annotated[Optional[UserClaims], Depends(require_auth)]) -> UserClaims:
    if settings.auth_disabled:
        return user or UserClaims(user_id="dev-platform", email="dev@local", platform_roles=["platform_admin"])
    if user is None or "platform_admin" not in (user.platform_roles or []):
        raise HTTPException(status_code=403, detail="platform_admin required")
    return user


