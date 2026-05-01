from __future__ import annotations

import asyncio
import time
import boto3
import structlog
from typing import TYPE_CHECKING
from uuid import UUID

from opensearchpy import AsyncOpenSearch
from opensearchpy import AWSV4SignerAsyncAuth
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.observability import system_event_writer
from loggator.security.connection_crypto import decrypt_secret

if TYPE_CHECKING:
    from loggator.db.models import TenantConnection, TenantIntegration

_SEARCH_INTEGRATION_PROVIDERS = frozenset({"opensearch", "elasticsearch", "wazuh_indexer"})

log = structlog.get_logger()


def build_opensearch_client(
    host: str,
    port: int,
    auth_type: str,
    *,
    use_ssl: bool,
    verify_certs: bool,
    ca_certs: str = "",
    username: str = "",
    password: str = "",
    api_key: str = "",
    aws_region: str = "us-east-1",
) -> AsyncOpenSearch:
    h = {"host": host, "port": port}
    common: dict = {
        "hosts": [h],
        "use_ssl": use_ssl,
        "verify_certs": verify_certs,
    }
    if ca_certs:
        common["ca_certs"] = ca_certs

    if auth_type == "none":
        return AsyncOpenSearch(**common)

    if auth_type == "basic":
        return AsyncOpenSearch(
            **common,
            http_auth=(username, password),
        )

    if auth_type == "api_key":
        return AsyncOpenSearch(
            **common,
            headers={"x-api-key": api_key},
        )

    if auth_type == "aws_iam":
        credentials = boto3.Session().get_credentials()
        aws_auth = AWSV4SignerAsyncAuth(credentials, aws_region, "es")
        return AsyncOpenSearch(**common, http_auth=aws_auth)

    raise ValueError(f"Unknown OPENSEARCH_AUTH_TYPE: {auth_type!r}")


def _build_client() -> AsyncOpenSearch:
    return build_opensearch_client(
        settings.opensearch_host,
        settings.opensearch_port,
        settings.opensearch_auth_type,
        use_ssl=settings.opensearch_use_ssl,
        verify_certs=settings.opensearch_verify_certs,
        ca_certs=settings.opensearch_ca_certs or "",
        username=settings.opensearch_username,
        password=settings.opensearch_password,
        api_key=settings.opensearch_api_key,
        aws_region=settings.aws_region,
    )


def _connection_row_is_configured(conn: "TenantConnection") -> bool:
    return bool(conn.opensearch_host and str(conn.opensearch_host).strip())


def _integration_row_is_search_configured(integ: "TenantIntegration") -> bool:
    if integ.provider not in _SEARCH_INTEGRATION_PROVIDERS:
        return False
    return bool(integ.opensearch_host and str(integ.opensearch_host).strip())


def build_opensearch_client_from_integration_row(integ: "TenantIntegration") -> AsyncOpenSearch:
    """Build AsyncOpenSearch from a TenantIntegration row (search providers only)."""
    auth = integ.opensearch_auth_type or "none"
    port = integ.opensearch_port if integ.opensearch_port is not None else settings.opensearch_port
    use_ssl = integ.opensearch_use_ssl if integ.opensearch_use_ssl is not None else settings.opensearch_use_ssl
    verify = (
        integ.opensearch_verify_certs if integ.opensearch_verify_certs is not None else settings.opensearch_verify_certs
    )
    pwd = decrypt_secret(integ.opensearch_password) or ""
    api_key = decrypt_secret(integ.opensearch_api_key) or ""
    ca = (decrypt_secret(integ.opensearch_ca_certs) or integ.opensearch_ca_certs or "") or ""
    region = integ.aws_region or settings.aws_region
    return build_opensearch_client(
        integ.opensearch_host or settings.opensearch_host,
        port,
        auth,
        use_ssl=use_ssl,
        verify_certs=verify,
        ca_certs=ca,
        username=integ.opensearch_username or "",
        password=pwd,
        api_key=api_key,
        aws_region=region,
    )


def _build_client_from_tenant_row(conn: "TenantConnection") -> AsyncOpenSearch:
    auth = conn.opensearch_auth_type or "none"
    port = conn.opensearch_port if conn.opensearch_port is not None else settings.opensearch_port
    use_ssl = conn.opensearch_use_ssl if conn.opensearch_use_ssl is not None else settings.opensearch_use_ssl
    verify = conn.opensearch_verify_certs if conn.opensearch_verify_certs is not None else settings.opensearch_verify_certs
    pwd = decrypt_secret(conn.opensearch_password) or settings.opensearch_password
    api_key = decrypt_secret(conn.opensearch_api_key) or settings.opensearch_api_key
    ca = (decrypt_secret(conn.opensearch_ca_certs) or conn.opensearch_ca_certs or "") or (settings.opensearch_ca_certs or "")
    region = conn.aws_region or settings.aws_region
    return build_opensearch_client(
        conn.opensearch_host or settings.opensearch_host,
        port,
        auth,
        use_ssl=use_ssl,
        verify_certs=verify,
        ca_certs=ca,
        username=conn.opensearch_username or settings.opensearch_username,
        password=pwd,
        api_key=api_key,
        aws_region=region,
    )


_client: AsyncOpenSearch | None = None
_last_build_failed = False

# Cached per-tenant clients. Timestamps drive a 5-minute TTL so rotated
# credentials are picked up without a process restart.
_tenant_clients: dict[UUID, AsyncOpenSearch] = {}
_tenant_client_timestamps: dict[UUID, float] = {}
_TENANT_CLIENT_TTL = 300.0  # seconds


async def _get_search_integration_row(session: AsyncSession, tenant_id: UUID) -> TenantIntegration | None:
    from loggator.db.models import TenantIntegration

    r = await session.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id, TenantIntegration.is_primary.is_(True))
        .limit(1)
    )
    prim = r.scalar_one_or_none()
    if prim is not None and _integration_row_is_search_configured(prim):
        return prim
    r2 = await session.execute(
        select(TenantIntegration)
        .where(TenantIntegration.tenant_id == tenant_id)
        .order_by(TenantIntegration.created_at.asc())
    )
    for row in r2.scalars().all():
        if _integration_row_is_search_configured(row):
            return row
    return None


async def get_effective_opensearch_display(session: AsyncSession, tenant_id: UUID) -> dict:
    """Redacted effective OpenSearch connection for UI: integration > tenant_connection > global defaults."""
    from loggator.db.models import TenantConnection

    integ = await _get_search_integration_row(session, tenant_id)
    if integ is not None:
        return {
            "configured": True,
            "source": "integration",
            "provider": integ.provider,
            "host": str(integ.opensearch_host or ""),
            "port": int(integ.opensearch_port) if integ.opensearch_port is not None else int(settings.opensearch_port),
            "auth_type": str(integ.opensearch_auth_type or settings.opensearch_auth_type or "none"),
            "use_ssl": bool(integ.opensearch_use_ssl)
            if integ.opensearch_use_ssl is not None
            else bool(settings.opensearch_use_ssl),
            "verify_certs": bool(integ.opensearch_verify_certs)
            if integ.opensearch_verify_certs is not None
            else bool(settings.opensearch_verify_certs),
        }

    result = await session.execute(select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1))
    conn = result.scalar_one_or_none()
    if conn is not None and _connection_row_is_configured(conn):
        return {
            "configured": True,
            "source": "tenant_connection",
            "provider": "opensearch",
            "host": str(conn.opensearch_host or ""),
            "port": int(conn.opensearch_port) if conn.opensearch_port is not None else int(settings.opensearch_port),
            "auth_type": str(conn.opensearch_auth_type or settings.opensearch_auth_type or "none"),
            "use_ssl": bool(conn.opensearch_use_ssl)
            if conn.opensearch_use_ssl is not None
            else bool(settings.opensearch_use_ssl),
            "verify_certs": bool(conn.opensearch_verify_certs)
            if conn.opensearch_verify_certs is not None
            else bool(settings.opensearch_verify_certs),
        }

    host = settings.opensearch_host or ""
    return {
        "configured": bool(host and str(host).strip()),
        "source": "global",
        "provider": "opensearch",
        "host": str(host),
        "port": int(settings.opensearch_port),
        "auth_type": str(settings.opensearch_auth_type or "none"),
        "use_ssl": bool(settings.opensearch_use_ssl),
        "verify_certs": bool(settings.opensearch_verify_certs),
    }


def get_client() -> AsyncOpenSearch:
    global _client, _last_build_failed
    if _client is None:
        try:
            _client = _build_client()
            log.info("opensearch.client.created", auth_type=settings.opensearch_auth_type)
            if _last_build_failed:
                asyncio.create_task(system_event_writer.write(
                    service="opensearch",
                    event_type="reconnected",
                    severity="info",
                    message="OpenSearch client reconnected after prior failure",
                    details={"auth_type": settings.opensearch_auth_type},
                ))
            _last_build_failed = False
        except Exception as exc:
            _last_build_failed = True
            asyncio.create_task(system_event_writer.write(
                service="opensearch",
                event_type="disconnected",
                severity="error",
                message=f"OpenSearch client failed to initialise: {exc}",
                details={
                    "host": settings.opensearch_host,
                    "port": settings.opensearch_port,
                    "error": str(exc),
                },
            ))
            raise
    return _client


async def get_opensearch_for_tenant(session: AsyncSession, tenant_id: UUID) -> AsyncOpenSearch:
    """Return OpenSearch client for ``tenant_id`` (integration > per-tenant connection > global)."""
    from loggator.db.models import TenantConnection

    integ = await _get_search_integration_row(session, tenant_id)
    if integ is not None:
        age = time.monotonic() - _tenant_client_timestamps.get(tenant_id, 0.0)
        if tenant_id not in _tenant_clients or age > _TENANT_CLIENT_TTL:
            old = _tenant_clients.pop(tenant_id, None)
            if old is not None:
                asyncio.create_task(old.close())
            _tenant_clients[tenant_id] = build_opensearch_client_from_integration_row(integ)
            _tenant_client_timestamps[tenant_id] = time.monotonic()
            log.info(
                "opensearch.tenant_client.created",
                tenant_id=str(tenant_id),
                source="integration",
                refreshed=old is not None,
            )
        return _tenant_clients[tenant_id]

    result = await session.execute(
        select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or not _connection_row_is_configured(row):
        return get_client()
    age = time.monotonic() - _tenant_client_timestamps.get(tenant_id, 0.0)
    if tenant_id not in _tenant_clients or age > _TENANT_CLIENT_TTL:
        old = _tenant_clients.pop(tenant_id, None)
        if old is not None:
            asyncio.create_task(old.close())
        _tenant_clients[tenant_id] = _build_client_from_tenant_row(row)
        _tenant_client_timestamps[tenant_id] = time.monotonic()
        log.info("opensearch.tenant_client.created", tenant_id=str(tenant_id), refreshed=old is not None)
    return _tenant_clients[tenant_id]


async def get_effective_index_pattern(session: AsyncSession, tenant_id: UUID) -> str:
    from loggator.db.models import TenantConnection

    integ = await _get_search_integration_row(session, tenant_id)
    if integ is not None and integ.opensearch_index_pattern and str(integ.opensearch_index_pattern).strip():
        return str(integ.opensearch_index_pattern).strip()

    result = await session.execute(
        select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1)
    )
    row = result.scalar_one_or_none()
    if row and row.opensearch_index_pattern and str(row.opensearch_index_pattern).strip():
        return str(row.opensearch_index_pattern).strip()
    return settings.opensearch_index_pattern


def invalidate_tenant_opensearch_client(tenant_id: UUID) -> None:
    """Drop cached AsyncOpenSearch for a tenant (e.g. after connection credentials change)."""
    _tenant_client_timestamps.pop(tenant_id, None)
    c = _tenant_clients.pop(tenant_id, None)
    if c is None:
        return
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(c.close())
    except RuntimeError:
        pass


async def close_all_clients() -> None:
    """Close all cached clients (call from app lifespan shutdown)."""
    global _client
    if _client is not None:
        await _client.close()
        _client = None
    for c in _tenant_clients.values():
        await c.close()
    _tenant_clients.clear()
    _tenant_client_timestamps.clear()
