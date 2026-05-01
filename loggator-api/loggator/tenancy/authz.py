"""Tenant authorization checks (no FastAPI ``Depends`` imports)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.tenancy.membership import subject_has_tenant_role


async def assert_tenant_admin_or_platform(
    session: AsyncSession,
    user: Optional[UserClaims],
    tenant_id: UUID,
) -> None:
    """Require platform JWT admin or ``tenant_admin`` membership row for ``tenant_id``."""
    if settings.auth_disabled:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if "platform_admin" in (user.platform_roles or []):
        return
    if await subject_has_tenant_role(session, user, tenant_id, {"tenant_admin"}):
        return
    raise HTTPException(status_code=403, detail="tenant_admin or platform_admin required")


async def assert_platform_or_membership_roles(
    session: AsyncSession,
    user: Optional[UserClaims],
    tenant_id: UUID,
    allowed_roles: set[str],
) -> None:
    """Allowed roles are membership roles, plus platform_admin JWT."""
    if settings.auth_disabled:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if "platform_admin" in (user.platform_roles or []):
        return
    if await subject_has_tenant_role(session, user, tenant_id, allowed_roles):
        return
    raise HTTPException(status_code=403, detail="Insufficient tenant role")
