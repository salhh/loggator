"""Platform / MSP tenant and connection CRUD."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_platform_or_msp
from loggator.auth.schemas import UserClaims
from loggator.db.models import Anomaly, Membership, Summary, Tenant, TenantApiKey, TenantConnection, User
from loggator.db.session import get_session
from loggator.opensearch.client import invalidate_tenant_opensearch_client
from loggator.security.connection_crypto import encrypt_secret
from loggator.tenancy.msp_scope import (
    assert_msp_or_platform_can_touch_tenant,
    get_tenant_or_404,
    is_platform_superadmin,
    tenant_ids_visible_to_principal,
)

router = APIRouter(prefix="/platform/tenants", tags=["platform"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    parent_tenant_id: UUID | None = None
    is_operator: bool = False
    created_at: datetime
    member_count: int = 0

    class Config:
        from_attributes = True


class TenantStatsOut(BaseModel):
    member_count: int
    anomaly_count: int
    summary_count: int
    api_key_count: int


class TenantCreate(BaseModel):
    name: str
    slug: str = Field(..., min_length=1, max_length=64)
    admin_subject: str | None = None
    admin_email: str | None = None
    parent_tenant_id: UUID | None = None
    is_operator: bool = False


class TenantPatch(BaseModel):
    name: str | None = None
    slug: str | None = Field(None, max_length=64)
    status: str | None = Field(None, pattern=r"^(active|suspended)$")


class TenantConnectionIn(BaseModel):
    opensearch_host: str | None = None
    opensearch_port: int | None = None
    opensearch_auth_type: str | None = Field(None, pattern=r"^(none|basic|api_key|aws_iam)$")
    opensearch_username: str | None = None
    opensearch_password: str | None = None
    opensearch_api_key: str | None = None
    opensearch_use_ssl: bool | None = None
    opensearch_verify_certs: bool | None = None
    opensearch_ca_certs: str | None = None
    aws_region: str | None = None
    opensearch_index_pattern: str | None = None


async def _upsert_user(session: AsyncSession, subject: str, email: str) -> User:
    r = await session.execute(select(User).where(User.subject == subject).limit(1))
    existing = r.scalar_one_or_none()
    if existing:
        return existing
    u = User(subject=subject, email=email or "")
    session.add(u)
    await session.flush()
    return u


@router.get("", response_model=list[TenantOut])
async def platform_list_tenants(
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    visible = await tenant_ids_visible_to_principal(session, user)
    member_count_sq = (
        select(Membership.tenant_id, func.count(Membership.id).label("cnt"))
        .group_by(Membership.tenant_id)
        .subquery()
    )
    q = (
        select(Tenant, func.coalesce(member_count_sq.c.cnt, 0).label("member_count"))
        .outerjoin(member_count_sq, Tenant.id == member_count_sq.c.tenant_id)
        .where(Tenant.deleted_at.is_(None))
        .order_by(Tenant.created_at.asc())
    )
    if visible is not None:
        q = q.where(Tenant.id.in_(visible))
    rows = (await session.execute(q)).all()
    result: list[TenantOut] = []
    for tenant, cnt in rows:
        out = TenantOut.model_validate(tenant)
        out.member_count = cnt
        result.append(out)
    return result


@router.post("", response_model=TenantOut)
async def platform_create_tenant(
    body: TenantCreate,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    dup = await session.execute(select(Tenant.id).where(Tenant.slug == body.slug).limit(1))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already in use")
    sup = is_platform_superadmin(user)
    if sup:
        is_op = body.is_operator
        parent: UUID | None = None if is_op else body.parent_tenant_id
        if not is_op and parent is None:
            raise HTTPException(status_code=422, detail="parent_tenant_id is required for customer tenants")
        if is_op and body.parent_tenant_id is not None:
            raise HTTPException(status_code=422, detail="operator tenant must not have parent_tenant_id")
    else:
        is_op = False
        parent = user.operator_tenant_id
        if parent is None:
            raise HTTPException(status_code=403, detail="MSP scope missing")
    if parent is not None:
        prow = await session.get(Tenant, parent)
        if prow is None or prow.deleted_at is not None:
            raise HTTPException(status_code=404, detail="Parent tenant not found")
    t = Tenant(
        name=body.name,
        slug=body.slug,
        status="active",
        parent_tenant_id=parent,
        is_operator=is_op,
    )
    session.add(t)
    await session.flush()
    if body.admin_subject:
        u = await _upsert_user(session, body.admin_subject.strip(), (body.admin_email or "").strip())
        session.add(Membership(user_id=u.id, tenant_id=t.id, role="tenant_admin"))
    await session.commit()
    await session.refresh(t)
    out = TenantOut.model_validate(t)
    out.member_count = 0
    return out


@router.get("/{tenant_id}", response_model=TenantOut)
async def platform_get_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    t = await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    cnt = (
        await session.execute(select(func.count(Membership.id)).where(Membership.tenant_id == tenant_id))
    ).scalar_one()
    out = TenantOut.model_validate(t)
    out.member_count = cnt
    return out


@router.patch("/{tenant_id}", response_model=TenantOut)
async def platform_patch_tenant(
    tenant_id: UUID,
    body: TenantPatch,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    t = await get_tenant_or_404(session, tenant_id)
    if body.name is not None:
        t.name = body.name
    if body.slug is not None:
        dup = await session.execute(
            select(Tenant.id).where(Tenant.slug == body.slug, Tenant.id != tenant_id).limit(1)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Slug already in use")
        t.slug = body.slug
    if body.status is not None:
        t.status = body.status
    await session.commit()
    await session.refresh(t)
    cnt = (
        await session.execute(select(func.count(Membership.id)).where(Membership.tenant_id == tenant_id))
    ).scalar_one()
    out = TenantOut.model_validate(t)
    out.member_count = cnt
    return out


@router.delete("/{tenant_id}")
async def platform_archive_tenant(
    tenant_id: UUID,
    hard: bool = Query(False, description="Super-admin hard delete (not implemented)"),
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    if hard:
        if not is_platform_superadmin(user):
            raise HTTPException(status_code=403, detail="hard delete requires platform_admin")
        raise HTTPException(status_code=501, detail="Hard delete is not implemented")
    t = await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    if t.is_operator:
        n = (
            await session.execute(
                select(func.count())
                .select_from(Tenant)
                .where(Tenant.parent_tenant_id == tenant_id, Tenant.deleted_at.is_(None))
            )
        ).scalar_one()
        if int(n or 0) > 0:
            raise HTTPException(
                status_code=400,
                detail="Cannot archive operator tenant while customer tenants exist",
            )
    t.deleted_at = datetime.now(timezone.utc)
    await session.commit()
    return {"ok": True, "tenant_id": str(tenant_id)}


@router.put("/{tenant_id}/connection", response_model=dict)
async def platform_put_connection(
    tenant_id: UUID,
    body: TenantConnectionIn,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    await get_tenant_or_404(session, tenant_id)
    r = await session.execute(select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1))
    conn = r.scalar_one_or_none()
    if conn is None:
        conn = TenantConnection(tenant_id=tenant_id)
        session.add(conn)
        await session.flush()

    data = body.model_dump(exclude_unset=True)
    for field in (
        "opensearch_host",
        "opensearch_port",
        "opensearch_auth_type",
        "opensearch_username",
        "opensearch_use_ssl",
        "opensearch_verify_certs",
        "aws_region",
        "opensearch_index_pattern",
    ):
        if field in data:
            setattr(conn, field, data[field])
    if "opensearch_password" in data and data["opensearch_password"] is not None:
        conn.opensearch_password = encrypt_secret(data["opensearch_password"])
    if "opensearch_api_key" in data and data["opensearch_api_key"] is not None:
        conn.opensearch_api_key = encrypt_secret(data["opensearch_api_key"])
    if "opensearch_ca_certs" in data and data["opensearch_ca_certs"] is not None:
        conn.opensearch_ca_certs = encrypt_secret(data["opensearch_ca_certs"])

    await session.commit()
    invalidate_tenant_opensearch_client(tenant_id)
    return {"ok": True, "tenant_id": str(tenant_id)}


@router.get("/{tenant_id}/stats", response_model=TenantStatsOut)
async def platform_tenant_stats(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    await get_tenant_or_404(session, tenant_id)

    member_count = (await session.execute(
        select(func.count(Membership.id)).where(Membership.tenant_id == tenant_id)
    )).scalar_one()
    anomaly_count = (await session.execute(
        select(func.count(Anomaly.id)).where(Anomaly.tenant_id == tenant_id)
    )).scalar_one()
    summary_count = (await session.execute(
        select(func.count(Summary.id)).where(Summary.tenant_id == tenant_id)
    )).scalar_one()
    api_key_count = (await session.execute(
        select(func.count(TenantApiKey.id)).where(
            TenantApiKey.tenant_id == tenant_id,
            TenantApiKey.revoked_at.is_(None),
        )
    )).scalar_one()

    return TenantStatsOut(
        member_count=member_count,
        anomaly_count=anomaly_count,
        summary_count=summary_count,
        api_key_count=api_key_count,
    )


@router.get("/{tenant_id}/connection")
async def platform_get_connection(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
):
    await assert_msp_or_platform_can_touch_tenant(session, user, tenant_id)
    await get_tenant_or_404(session, tenant_id)

    r = await session.execute(select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1))
    conn = r.scalar_one_or_none()
    if conn is None:
        return None

    return {
        "opensearch_host": conn.opensearch_host,
        "opensearch_port": conn.opensearch_port,
        "opensearch_auth_type": conn.opensearch_auth_type,
        "opensearch_username": conn.opensearch_username,
        "opensearch_password": "***" if conn.opensearch_password else None,
        "opensearch_api_key": "***" if conn.opensearch_api_key else None,
        "opensearch_use_ssl": conn.opensearch_use_ssl,
        "opensearch_verify_certs": conn.opensearch_verify_certs,
        "opensearch_ca_certs": "***" if conn.opensearch_ca_certs else None,
        "aws_region": conn.aws_region,
        "opensearch_index_pattern": conn.opensearch_index_pattern,
    }
