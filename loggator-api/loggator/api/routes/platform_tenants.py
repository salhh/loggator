"""Platform-admin tenant and connection CRUD."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_platform_admin
from loggator.auth.schemas import UserClaims
from loggator.db.models import Membership, Tenant, TenantConnection, User
from loggator.db.session import get_session
from loggator.opensearch.client import invalidate_tenant_opensearch_client
from loggator.security.connection_crypto import encrypt_secret

router = APIRouter(prefix="/platform/tenants", tags=["platform"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class TenantCreate(BaseModel):
    name: str
    slug: str = Field(..., min_length=1, max_length=64)
    admin_subject: str | None = None
    admin_email: str | None = None


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
    _: UserClaims = Depends(require_platform_admin),
):
    result = await session.execute(select(Tenant).order_by(Tenant.created_at.asc()))
    return list(result.scalars().all())


@router.post("", response_model=TenantOut)
async def platform_create_tenant(
    body: TenantCreate,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_admin),
):
    dup = await session.execute(select(Tenant.id).where(Tenant.slug == body.slug).limit(1))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Slug already in use")
    t = Tenant(name=body.name, slug=body.slug, status="active")
    session.add(t)
    await session.flush()
    if body.admin_subject:
        u = await _upsert_user(session, body.admin_subject.strip(), (body.admin_email or "").strip())
        session.add(Membership(user_id=u.id, tenant_id=t.id, role="tenant_admin"))
    await session.commit()
    await session.refresh(t)
    return t


@router.get("/{tenant_id}", response_model=TenantOut)
async def platform_get_tenant(
    tenant_id: UUID,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_admin),
):
    t = await session.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return t


@router.patch("/{tenant_id}", response_model=TenantOut)
async def platform_patch_tenant(
    tenant_id: UUID,
    body: TenantPatch,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_admin),
):
    t = await session.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
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
    return t


@router.put("/{tenant_id}/connection", response_model=dict)
async def platform_put_connection(
    tenant_id: UUID,
    body: TenantConnectionIn,
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_admin),
):
    t = await session.get(Tenant, tenant_id)
    if t is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
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
