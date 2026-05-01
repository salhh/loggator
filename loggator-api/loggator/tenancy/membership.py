"""Resolve OIDC subject to local user rows and tenant membership."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.schemas import UserClaims
from loggator.db.models import Membership, Tenant, User
from loggator.tenancy.msp_scope import is_msp_admin, is_platform_superadmin


async def get_or_create_user(session: AsyncSession, subject: str, email: str | None) -> tuple[User, bool]:
    """Return (user, created) — upserts a User row for the given OIDC subject."""
    r = await session.execute(select(User).where(User.subject == subject).limit(1))
    user = r.scalar_one_or_none()
    if user is not None:
        return user, False
    user = User(subject=subject, email=email or "")
    session.add(user)
    await session.flush()
    return user, True


async def ensure_default_membership(session: AsyncSession, user: User) -> None:
    """Create a tenant_member Membership for the bootstrap tenant if none exists."""
    from loggator.tenancy.bootstrap import get_default_tenant_id

    try:
        tenant_id = await get_default_tenant_id(session)
    except RuntimeError:
        return
    exists = await session.execute(
        select(Membership.id)
        .where(Membership.user_id == user.id, Membership.tenant_id == tenant_id)
        .limit(1)
    )
    if exists.scalar_one_or_none() is None:
        session.add(Membership(user_id=user.id, tenant_id=tenant_id, role="tenant_member"))
        await session.flush()


async def get_internal_user_id(session: AsyncSession, subject: str) -> UUID | None:
    if not subject:
        return None
    r = await session.execute(select(User.id).where(User.subject == subject).limit(1))
    return r.scalar_one_or_none()


async def user_can_access_tenant(session: AsyncSession, user: UserClaims, tenant_id: UUID) -> bool:
    if is_platform_superadmin(user):
        return True
    if is_msp_admin(user) and user.operator_tenant_id:
        t = await session.get(Tenant, tenant_id)
        if t is None or t.deleted_at is not None:
            return False
        if t.id == user.operator_tenant_id or t.parent_tenant_id == user.operator_tenant_id:
            return True
    uid = await get_internal_user_id(session, user.user_id)
    if uid is None:
        return False
    r = await session.execute(
        select(Membership.id).where(Membership.user_id == uid, Membership.tenant_id == tenant_id).limit(1)
    )
    return r.scalar_one_or_none() is not None


async def get_membership_for_subject(
    session: AsyncSession, subject: str, tenant_id: UUID
) -> Membership | None:
    uid = await get_internal_user_id(session, subject)
    if uid is None:
        return None
    r = await session.execute(
        select(Membership).where(Membership.user_id == uid, Membership.tenant_id == tenant_id).limit(1)
    )
    return r.scalar_one_or_none()


async def subject_has_tenant_role(
    session: AsyncSession, user: UserClaims, tenant_id: UUID, roles: set[str]
) -> bool:
    if is_platform_superadmin(user):
        return True
    if is_msp_admin(user) and user.operator_tenant_id:
        t = await session.get(Tenant, tenant_id)
        if t and t.deleted_at is None:
            op = user.operator_tenant_id
            if t.id == op or t.parent_tenant_id == op:
                return True
    m = await get_membership_for_subject(session, user.user_id, tenant_id)
    if m is None:
        return False
    return m.role in roles


async def count_tenant_admins(session: AsyncSession, tenant_id: UUID) -> int:
    r = await session.execute(
        select(func.count())
        .select_from(Membership)
        .where(Membership.tenant_id == tenant_id, Membership.role == "tenant_admin")
    )
    return int(r.scalar_one() or 0)
