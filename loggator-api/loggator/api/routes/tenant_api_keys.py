"""Tenant-scoped API keys (ingest scope)."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.security.api_key_hash import hash_ingest_api_key
from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import TenantApiKey
from loggator.db.session import get_session
from loggator.tenancy.deps import get_effective_tenant_id
from loggator.tenancy.authz import assert_tenant_admin_or_platform

router = APIRouter(prefix="/tenant-api-keys", tags=["tenant-api-keys"])


class TenantApiKeyCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    scopes: list[str] = Field(default_factory=lambda: ["ingest"])


class TenantApiKeyCreated(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    key: str
    scopes: list[str]
    created_at: datetime


class TenantApiKeyListItem(BaseModel):
    id: UUID
    name: str
    key_prefix: str
    scopes: list
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None

    class Config:
        from_attributes = True


@router.post("", response_model=TenantApiKeyCreated)
async def create_tenant_api_key(
    body: TenantApiKeyCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    raw = "lgk_" + secrets.token_urlsafe(24)
    row = TenantApiKey(
        tenant_id=tenant_id,
        name=body.name.strip(),
        key_prefix=raw[:16],
        key_hash=hash_ingest_api_key(raw),
        scopes=list(body.scopes) if body.scopes else ["ingest"],
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return TenantApiKeyCreated(
        id=row.id,
        name=row.name,
        key_prefix=row.key_prefix,
        key=raw,
        scopes=row.scopes if isinstance(row.scopes, list) else [],
        created_at=row.created_at,
    )


@router.get("", response_model=list[TenantApiKeyListItem])
async def list_tenant_api_keys(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(TenantApiKey)
        .where(TenantApiKey.tenant_id == tenant_id)
        .order_by(TenantApiKey.created_at.desc())
    )
    return list(r.scalars().all())


@router.post("/{key_id}/revoke", response_model=dict)
async def revoke_tenant_api_key(
    key_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(TenantApiKey).where(TenantApiKey.id == key_id, TenantApiKey.tenant_id == tenant_id).limit(1)
    )
    row = r.scalar_one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="API key not found")
    row.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    return {"ok": True}
