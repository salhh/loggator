"""Tenant authorization checks (no FastAPI ``Depends`` imports)."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Tenant
from loggator.tenancy.membership import subject_has_tenant_role
from loggator.tenancy.msp_scope import is_msp_admin, is_platform_superadmin


async def _msp_can_administer_tenant(session: AsyncSession, user: UserClaims, tenant_id: UUID) -> bool:
    """MSP admin may manage their operator row and any non-deleted tenant in their subtree."""
    if not is_msp_admin(user) or user.operator_tenant_id is None:
        return False
    t = await session.get(Tenant, tenant_id)
    if t is None or t.deleted_at is not None:
        return False
    op = user.operator_tenant_id
    return t.id == op or t.parent_tenant_id == op


async def assert_tenant_admin_or_platform(
    session: AsyncSession,
    user: Optional[UserClaims],
    tenant_id: UUID,
) -> None:
    """Require platform JWT admin, MSP admin for this customer tenant, or ``tenant_admin`` membership."""
    if settings.auth_disabled:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if is_platform_superadmin(user):
        return
    if await _msp_can_administer_tenant(session, user, tenant_id):
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
    """Allowed roles are membership roles, plus platform_admin JWT, plus MSP admin for subtree."""
    if settings.auth_disabled:
        return
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if is_platform_superadmin(user):
        return
    if await _msp_can_administer_tenant(session, user, tenant_id):
        return
    if await subject_has_tenant_role(session, user, tenant_id, allowed_roles):
        return
    raise HTTPException(status_code=403, detail="Insufficient tenant role")
