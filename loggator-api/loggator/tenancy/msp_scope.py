"""Multi-MSP scoping: operator tenants own customer tenants via parent_tenant_id."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Membership, Tenant, User


def is_platform_superadmin(user: UserClaims | None) -> bool:
    return bool(user and "platform_admin" in (user.platform_roles or []))


def is_msp_admin(user: UserClaims | None) -> bool:
    return bool(user and "msp_admin" in (user.platform_roles or []) and user.operator_tenant_id)


def msp_operator_id(user: UserClaims | None) -> UUID | None:
    if not user:
        return None
    return user.operator_tenant_id


async def tenant_ids_visible_to_msp(session: AsyncSession, operator_tenant_id: UUID) -> list[UUID]:
    """Operator tenant id plus all non-deleted customer tenant ids under that operator."""
    r = await session.execute(
        select(Tenant.id).where(
            Tenant.deleted_at.is_(None),
            or_(
                Tenant.id == operator_tenant_id,
                Tenant.parent_tenant_id == operator_tenant_id,
            ),
        )
    )
    return list(r.scalars().all())


async def tenant_ids_visible_to_principal(session: AsyncSession, user: UserClaims | None) -> list[UUID] | None:
    """
    None = no filter (global platform admin or auth off).
    Otherwise list of tenant UUIDs the principal may reference in platform APIs.
    """
    if settings.auth_disabled or user is None:
        return None
    if is_platform_superadmin(user):
        return None
    if is_msp_admin(user) and user.operator_tenant_id:
        return await tenant_ids_visible_to_msp(session, user.operator_tenant_id)
    return []


async def get_tenant_or_404(session: AsyncSession, tenant_id: UUID) -> Tenant:
    t = await session.get(Tenant, tenant_id)
    if t is None or t.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t


async def assert_msp_or_platform_can_touch_tenant(
    session: AsyncSession,
    user: UserClaims | None,
    tenant_id: UUID,
) -> Tenant:
    t = await get_tenant_or_404(session, tenant_id)
    if settings.auth_disabled or user is None:
        return t
    if is_platform_superadmin(user):
        return t
    if is_msp_admin(user) and user.operator_tenant_id:
        op = user.operator_tenant_id
        if t.id == op or t.parent_tenant_id == op:
            return t
        raise HTTPException(status_code=403, detail="Tenant not in your organization")
    raise HTTPException(status_code=403, detail="Insufficient permissions")


async def msp_customer_tenant_ids(session: AsyncSession, operator_tenant_id: UUID) -> list[UUID]:
    r = await session.execute(
        select(Tenant.id).where(
            Tenant.parent_tenant_id == operator_tenant_id,
            Tenant.deleted_at.is_(None),
            Tenant.is_operator.is_(False),
        )
    )
    return list(r.scalars().all())


async def resolve_operator_tenant_id_for_subject(session: AsyncSession, subject: str) -> UUID | None:
    """First msp_admin membership on an operator tenant for this subject (deterministic order)."""
    r = await session.execute(
        select(Tenant.id)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .join(User, User.id == Membership.user_id)
        .where(
            User.subject == subject,
            Membership.role == "msp_admin",
            Tenant.is_operator.is_(True),
            Tenant.deleted_at.is_(None),
        )
        .order_by(Membership.created_at.asc())
        .limit(1)
    )
    return r.scalar_one_or_none()


async def enrich_user_msp_from_db(session: AsyncSession, user: UserClaims) -> UserClaims:
    """Attach ``operator_tenant_id`` + ``msp_admin`` from DB when JWT omits operator (OIDC-friendly)."""
    if user.operator_tenant_id is not None:
        return user
    op_id = await resolve_operator_tenant_id_for_subject(session, user.user_id)
    if op_id is None:
        return user
    pr = list(user.platform_roles or [])
    if "msp_admin" not in pr:
        pr = [*pr, "msp_admin"]
    return user.model_copy(update={"operator_tenant_id": op_id, "platform_roles": pr})
