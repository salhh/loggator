"""Tenants visible to the current principal (for UI tenant switching)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Membership, Tenant
from loggator.db.session import get_session
from loggator.tenancy.membership import get_internal_user_id
from loggator.tenancy.msp_scope import is_msp_admin, is_platform_superadmin

router = APIRouter(tags=["tenants"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    parent_tenant_id: UUID | None = None
    is_operator: bool = False
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/tenants", response_model=list[TenantOut])
async def list_accessible_tenants(
    session: AsyncSession = Depends(get_session),
    user: Optional[UserClaims] = Depends(require_auth),
):
    """
    Tenants the caller may use with ``X-Tenant-Id`` (or sole tenant when only one).

    - Auth disabled: all active, non-deleted tenants (local dev).
    - ``platform_admin``: all active, non-deleted tenants.
    - ``msp_admin``: operator tenant, its customer tenants, plus any membership tenants.
    - Otherwise: tenants with a membership row for the OIDC subject.
    """
    q_base = (
        select(Tenant)
        .where(Tenant.status == "active", Tenant.deleted_at.is_(None))
        .order_by(Tenant.name.asc())
    )
    if settings.auth_disabled or user is None:
        result = await session.execute(q_base)
        return list(result.scalars().all())
    if is_platform_superadmin(user):
        result = await session.execute(q_base)
        return list(result.scalars().all())
    if is_msp_admin(user) and user.operator_tenant_id:
        op = user.operator_tenant_id
        conds = [Tenant.id == op, Tenant.parent_tenant_id == op]
        uid = await get_internal_user_id(session, user.user_id)
        if uid:
            conds.append(Tenant.id.in_(select(Membership.tenant_id).where(Membership.user_id == uid)))
        q = (
            select(Tenant)
            .where(
                Tenant.deleted_at.is_(None),
                Tenant.status == "active",
                or_(*conds),
            )
            .order_by(Tenant.name.asc())
        )
        result = await session.execute(q)
        return list(result.scalars().all())
    uid = await get_internal_user_id(session, user.user_id)
    if uid is None:
        return []
    q = (
        select(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(
            Membership.user_id == uid,
            Tenant.status == "active",
            Tenant.deleted_at.is_(None),
        )
        .order_by(Tenant.name.asc())
    )
    result = await session.execute(q)
    return list(result.scalars().all())
