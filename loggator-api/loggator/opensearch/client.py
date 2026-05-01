import asyncio
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

if TYPE_CHECKING:
    from loggator.db.models import TenantConnection

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


def _build_client_from_tenant_row(conn: "TenantConnection") -> AsyncOpenSearch:
    auth = conn.opensearch_auth_type or "none"
    port = conn.opensearch_port if conn.opensearch_port is not None else settings.opensearch_port
    use_ssl = conn.opensearch_use_ssl if conn.opensearch_use_ssl is not None else settings.opensearch_use_ssl
    verify = conn.opensearch_verify_certs if conn.opensearch_verify_certs is not None else settings.opensearch_verify_certs
    ca = (conn.opensearch_ca_certs or "") or (settings.opensearch_ca_certs or "")
    region = conn.aws_region or settings.aws_region
    return build_opensearch_client(
        conn.opensearch_host or settings.opensearch_host,
        port,
        auth,
        use_ssl=use_ssl,
        verify_certs=verify,
        ca_certs=ca,
        username=conn.opensearch_username or settings.opensearch_username,
        password=conn.opensearch_password or settings.opensearch_password,
        api_key=conn.opensearch_api_key or settings.opensearch_api_key,
        aws_region=region,
    )


_client: AsyncOpenSearch | None = None
_last_build_failed = False

# Cached clients for tenants that override OpenSearch (invalidated only on process restart).
_tenant_clients: dict[UUID, AsyncOpenSearch] = {}


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
    """Return OpenSearch client for ``tenant_id`` (per-tenant connection or global fallback)."""
    from loggator.db.models import TenantConnection

    result = await session.execute(
        select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None or not _connection_row_is_configured(row):
        return get_client()
    if tenant_id not in _tenant_clients:
        _tenant_clients[tenant_id] = _build_client_from_tenant_row(row)
        log.info("opensearch.tenant_client.created", tenant_id=str(tenant_id))
    return _tenant_clients[tenant_id]


async def get_effective_index_pattern(session: AsyncSession, tenant_id: UUID) -> str:
    from loggator.db.models import TenantConnection

    result = await session.execute(
        select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1)
    )
    row = result.scalar_one_or_none()
    if row and row.opensearch_index_pattern and str(row.opensearch_index_pattern).strip():
        return str(row.opensearch_index_pattern).strip()
    return settings.opensearch_index_pattern


async def close_client() -> None:
    global _client, _tenant_clients
    if _client is not None:
        await _client.close()
        _client = None
    for c in _tenant_clients.values():
        await c.close()
    _tenant_clients.clear()
