"""Tenant-scoped log/SIEM integrations (OpenSearch-compatible + Wazuh API stub)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import TenantIntegration
from loggator.db.session import get_session
from loggator.opensearch.client import build_opensearch_client_from_integration_row, invalidate_tenant_opensearch_client
from loggator.security.connection_crypto import encrypt_secret
from loggator.tenancy.authz import assert_tenant_admin_or_platform
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(prefix="/tenant/integrations", tags=["integrations"])

_SEARCH_PROVIDERS = frozenset({"opensearch", "elasticsearch", "wazuh_indexer"})
_ALL_PROVIDERS = _SEARCH_PROVIDERS | {"wazuh_api"}


class IntegrationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    provider: str
    is_primary: bool
    extra_config: dict[str, Any] | None
    opensearch_host: str | None
    opensearch_port: int | None
    opensearch_auth_type: str | None
    opensearch_username: str | None
    opensearch_use_ssl: bool | None
    opensearch_verify_certs: bool | None
    aws_region: str | None
    opensearch_index_pattern: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class IntegrationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider: str = Field(..., pattern=r"^(opensearch|elasticsearch|wazuh_indexer|wazuh_api)$")
    is_primary: bool = False
    extra_config: dict[str, Any] | None = None
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


class IntegrationPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=128)
    is_primary: bool | None = None
    extra_config: dict[str, Any] | None = None
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


async def _clear_other_primary(session: AsyncSession, tenant_id: UUID, keep_id: UUID | None) -> None:
    q = select(TenantIntegration).where(
        TenantIntegration.tenant_id == tenant_id,
        TenantIntegration.is_primary.is_(True),
    )
    if keep_id:
        q = q.where(TenantIntegration.id != keep_id)
    rows = (await session.execute(q)).scalars().all()
    for r in rows:
        r.is_primary = False


def _encrypt_if_set(val: str | None) -> str | None:
    if val is None:
        return None
    return encrypt_secret(val)


@router.get("", response_model=list[IntegrationOut])
async def list_integrations(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    r = await session.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
        .order_by(TenantIntegration.is_primary.desc(), TenantIntegration.name.asc())
    )
    return list(r.scalars().all())


@router.post("", response_model=IntegrationOut)
async def create_integration(
    body: IntegrationCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    if body.provider not in _ALL_PROVIDERS:
        raise HTTPException(status_code=422, detail="Invalid provider")
    dup = await session.execute(
        select(TenantIntegration.id).where(
            TenantIntegration.tenant_id == tenant_id,
            TenantIntegration.name == body.name.strip(),
        ).limit(1)
    )
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Integration name already exists for tenant")

    if body.is_primary:
        await _clear_other_primary(session, tenant_id, None)

    row = TenantIntegration(
        tenant_id=tenant_id,
        name=body.name.strip(),
        provider=body.provider,
        is_primary=body.is_primary,
        extra_config=body.extra_config,
        opensearch_host=body.opensearch_host,
        opensearch_port=body.opensearch_port,
        opensearch_auth_type=body.opensearch_auth_type,
        opensearch_username=body.opensearch_username,
        opensearch_password=_encrypt_if_set(body.opensearch_password) if body.opensearch_password else None,
        opensearch_api_key=_encrypt_if_set(body.opensearch_api_key) if body.opensearch_api_key else None,
        opensearch_use_ssl=body.opensearch_use_ssl,
        opensearch_verify_certs=body.opensearch_verify_certs,
        opensearch_ca_certs=_encrypt_if_set(body.opensearch_ca_certs) if body.opensearch_ca_certs else None,
        aws_region=body.aws_region,
        opensearch_index_pattern=body.opensearch_index_pattern,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    invalidate_tenant_opensearch_client(tenant_id)
    return row


@router.patch("/{integration_id}", response_model=IntegrationOut)
async def patch_integration(
    integration_id: UUID,
    body: IntegrationPatch,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    row = await session.get(TenantIntegration, integration_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Integration not found")
    if body.name is not None:
        dup = await session.execute(
            select(TenantIntegration.id).where(
                TenantIntegration.tenant_id == tenant_id,
                TenantIntegration.name == body.name.strip(),
                TenantIntegration.id != integration_id,
            ).limit(1)
        )
        if dup.scalar_one_or_none():
            raise HTTPException(status_code=409, detail="Integration name already exists")
        row.name = body.name.strip()
    if body.is_primary is True:
        await _clear_other_primary(session, tenant_id, row.id)
        row.is_primary = True
    elif body.is_primary is False:
        row.is_primary = False
    if body.extra_config is not None:
        row.extra_config = body.extra_config
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
        val = getattr(body, field)
        if val is not None:
            setattr(row, field, val)
    if body.opensearch_password is not None:
        row.opensearch_password = _encrypt_if_set(body.opensearch_password) if body.opensearch_password else None
    if body.opensearch_api_key is not None:
        row.opensearch_api_key = _encrypt_if_set(body.opensearch_api_key) if body.opensearch_api_key else None
    if body.opensearch_ca_certs is not None:
        row.opensearch_ca_certs = _encrypt_if_set(body.opensearch_ca_certs) if body.opensearch_ca_certs else None

    row.updated_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(row)
    invalidate_tenant_opensearch_client(tenant_id)
    return row


@router.delete("/{integration_id}")
async def delete_integration(
    integration_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
):
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    row = await session.get(TenantIntegration, integration_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Integration not found")
    await session.delete(row)
    await session.commit()
    invalidate_tenant_opensearch_client(tenant_id)
    return {"ok": True}


async def _test_search_cluster(row: TenantIntegration) -> dict[str, Any]:
    client = build_opensearch_client_from_integration_row(row)
    try:
        info = await client.info()
        await client.close()
        return {"ok": True, "cluster_name": info.get("cluster_name"), "version": info.get("version", {}).get("number")}
    except Exception as e:
        try:
            await client.close()
        except Exception:
            pass
        raise HTTPException(status_code=502, detail=f"Cluster unreachable: {e}") from e


@router.post("/{integration_id}/test")
async def test_integration(
    integration_id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: UserClaims | None = Depends(require_auth),
) -> dict[str, Any]:
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    row = await session.get(TenantIntegration, integration_id)
    if row is None or row.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Integration not found")
    if row.provider in _SEARCH_PROVIDERS:
        return await _test_search_cluster(row)
    if row.provider == "wazuh_api":
        base = (row.extra_config or {}).get("base_url") or (row.extra_config or {}).get("wazuh_api_base")
        if not base or not str(base).strip():
            raise HTTPException(status_code=400, detail="extra_config.base_url required for wazuh_api")
        url = str(base).rstrip("/") + "/"
        try:
            async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                r = await client.get(url)
            return {"ok": r.status_code < 500, "status_code": r.status_code, "detail": "Wazuh API reachability check"}
        except Exception as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
    raise HTTPException(status_code=400, detail="Unknown provider")
