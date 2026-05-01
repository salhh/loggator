"""Tenant membership CRUD (effective tenant from JWT + X-Tenant-Id)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import Membership, User
from loggator.db.session import get_session
from loggator.tenancy.deps import get_effective_tenant_id
from loggator.tenancy.membership import count_tenant_admins, get_membership_for_subject
from loggator.tenancy.authz import assert_platform_or_membership_roles, assert_tenant_admin_or_platform
from loggator.tenancy.msp_scope import is_msp_admin

router = APIRouter(prefix="/tenant/members", tags=["tenant-members"])

_VALID_ROLES = frozenset({"tenant_admin", "tenant_member"})


class MemberOut(BaseModel):
    membership_id: UUID
    user_id: UUID
    subject: str
    email: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class MemberCreate(BaseModel):
    subject: str = Field(..., min_length=1, max_length=255)
    email: str = ""
    role: str = Field(default="tenant_member", pattern=r"^(tenant_admin|tenant_member)$")


class MemberPatch(BaseModel):
    role: str = Field(..., pattern=r"^(tenant_admin|tenant_member)$")


def _is_platform_or_msp_elevated(user: UserClaims | None) -> bool:
    if not user:
        return False
    if "platform_admin" in (user.platform_roles or []):
        return True
    return is_msp_admin(user)


@router.get("", response_model=list[MemberOut])
async def list_tenant_members(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_platform_or_membership_roles(
        session, user, tenant_id, {"tenant_admin", "tenant_member"}
    )
    result = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.tenant_id == tenant_id)
        .order_by(Membership.created_at.asc())
    )
    out: list[MemberOut] = []
    for m, u in result.all():
        out.append(
            MemberOut(
                membership_id=m.id,
                user_id=u.id,
                subject=u.subject,
                email=u.email or "",
                role=m.role,
                created_at=m.created_at,
            )
        )
    return out


@router.post("", response_model=MemberOut)
async def add_tenant_member(
    body: MemberCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    subj = body.subject.strip()
    existing_m = await get_membership_for_subject(session, subj, tenant_id)
    if existing_m is not None:
        raise HTTPException(status_code=409, detail="User already a member of this tenant")

    r = await session.execute(select(User).where(User.subject == subj).limit(1))
    u = r.scalar_one_or_none()
    if u is None:
        u = User(subject=subj, email=(body.email or "").strip())
        session.add(u)
        await session.flush()
    elif body.email and body.email.strip():
        u.email = body.email.strip()

    m = Membership(user_id=u.id, tenant_id=tenant_id, role=body.role)
    session.add(m)
    await session.commit()
    await session.refresh(m)
    await session.refresh(u)
    return MemberOut(
        membership_id=m.id,
        user_id=u.id,
        subject=u.subject,
        email=u.email or "",
        role=m.role,
        created_at=m.created_at,
    )


@router.patch("/{membership_id}", response_model=MemberOut)
async def patch_tenant_member(
    membership_id: UUID,
    body: MemberPatch,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.id == membership_id, Membership.tenant_id == tenant_id)
        .limit(1)
    )
    row = r.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    m, u = row
    if m.role == "tenant_admin" and body.role == "tenant_member":
        n = await count_tenant_admins(session, tenant_id)
        if n <= 1 and not _is_platform_or_msp_elevated(user):
            raise HTTPException(
                status_code=400,
                detail="Cannot demote the last tenant_admin; add another admin or contact your MSP",
            )
    m.role = body.role
    await session.commit()
    await session.refresh(m)
    return MemberOut(
        membership_id=m.id,
        user_id=u.id,
        subject=u.subject,
        email=u.email or "",
        role=m.role,
        created_at=m.created_at,
    )


@router.delete("/{membership_id}", response_model=dict)
async def remove_tenant_member(
    membership_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(Membership).where(Membership.id == membership_id, Membership.tenant_id == tenant_id).limit(1)
    )
    m = r.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=404, detail="Membership not found")
    if m.role == "tenant_admin":
        n = await count_tenant_admins(session, tenant_id)
        if n <= 1 and not _is_platform_or_msp_elevated(user):
            raise HTTPException(
                status_code=400,
                detail="Cannot remove the last tenant_admin; add another admin or contact your MSP",
            )
    await session.delete(m)
    await session.commit()
    return {"ok": True}
