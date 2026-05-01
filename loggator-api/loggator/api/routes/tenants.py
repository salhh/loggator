"""Tenants visible to the current principal (for UI tenant switching)."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Membership, Tenant
from loggator.db.session import get_session
from loggator.tenancy.membership import get_internal_user_id

router = APIRouter(tags=["tenants"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
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

    - Auth disabled: all active tenants (local dev).
    - ``platform_admin``: all active tenants.
    - Otherwise: tenants with a membership row for the OIDC subject.
    """
    q_base = select(Tenant).where(Tenant.status == "active").order_by(Tenant.name.asc())
    if settings.auth_disabled or user is None:
        result = await session.execute(q_base)
        return list(result.scalars().all())
    if "platform_admin" in (user.platform_roles or []):
        result = await session.execute(q_base)
        return list(result.scalars().all())
    uid = await get_internal_user_id(session, user.user_id)
    if uid is None:
        return []
    q = (
        select(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .where(Membership.user_id == uid, Tenant.status == "active")
        .order_by(Tenant.name.asc())
    )
    result = await session.execute(q)
    return list(result.scalars().all())
