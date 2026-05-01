"""OpenSearch per-tenant client cache: 5-minute TTL + invalidation."""

import time
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_session(conn_row=None):
    """Return a mock AsyncSession whose execute returns conn_row."""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = conn_row
    session.execute = AsyncMock(return_value=result)
    return session


def _make_conn_row(host="os-host"):
    """Return a minimal TenantConnection-like object that is 'configured'."""
    row = MagicMock()
    row.opensearch_host = host
    row.opensearch_port = 9200
    row.opensearch_auth_type = "none"
    row.opensearch_use_ssl = False
    row.opensearch_verify_certs = False
    row.opensearch_ca_certs = None
    row.opensearch_username = ""
    row.opensearch_password = None
    row.opensearch_api_key = None
    row.aws_region = "us-east-1"
    row.opensearch_index_pattern = "logs-*"
    return row


@pytest.mark.asyncio
async def test_tenant_client_is_cached_within_ttl():
    """The same client object is returned on a second call within the TTL."""
    import loggator.opensearch.client as mod

    tid = uuid4()
    fake_client = MagicMock()
    conn = _make_conn_row()
    session = _make_session(conn)

    mod._tenant_clients.clear()
    mod._tenant_client_timestamps.clear()

    with patch.object(mod, "_build_client_from_tenant_row", return_value=fake_client) as mock_build:
        first = await mod.get_opensearch_for_tenant(session, tid)
        second = await mod.get_opensearch_for_tenant(session, tid)

        assert first is fake_client
        assert second is fake_client
        # _build_client_from_tenant_row must be called only once (cache hit on second)
        assert mock_build.call_count == 1


@pytest.mark.asyncio
async def test_tenant_client_rebuilt_after_ttl_expires():
    """A new client is created once the TTL has elapsed."""
    import loggator.opensearch.client as mod

    tid = uuid4()
    old_client = MagicMock()
    new_client = MagicMock()
    old_client.close = AsyncMock()
    conn = _make_conn_row()
    session = _make_session(conn)

    mod._tenant_clients.clear()
    mod._tenant_client_timestamps.clear()

    build_mock = MagicMock(return_value=new_client)
    with patch.object(mod, "_build_client_from_tenant_row", build_mock):
        # Seed the cache with a timestamp that is already past the TTL
        mod._tenant_clients[tid] = old_client
        mod._tenant_client_timestamps[tid] = time.monotonic() - (mod._TENANT_CLIENT_TTL + 1)

        rebuilt = await mod.get_opensearch_for_tenant(session, tid)

        assert rebuilt is new_client
        assert build_mock.call_count == 1


@pytest.mark.asyncio
async def test_invalidate_removes_client_and_timestamp():
    """invalidate_tenant_opensearch_client clears both the client and its timestamp."""
    import loggator.opensearch.client as mod

    tid = uuid4()
    fake_client = MagicMock()
    fake_client.close = AsyncMock()

    mod._tenant_clients[tid] = fake_client
    mod._tenant_client_timestamps[tid] = time.monotonic()

    mod.invalidate_tenant_opensearch_client(tid)

    assert tid not in mod._tenant_clients
    assert tid not in mod._tenant_client_timestamps


@pytest.mark.asyncio
async def test_close_all_clients_clears_everything():
    """close_all_clients closes every cached client and resets all state."""
    import loggator.opensearch.client as mod

    tid1, tid2 = uuid4(), uuid4()
    c1, c2 = AsyncMock(), AsyncMock()

    mod._tenant_clients = {tid1: c1, tid2: c2}
    mod._tenant_client_timestamps = {tid1: time.monotonic(), tid2: time.monotonic()}
    mod._client = AsyncMock()
    global_client = mod._client

    await mod.close_all_clients()

    global_client.close.assert_called_once()
    c1.close.assert_called_once()
    c2.close.assert_called_once()
    assert mod._tenant_clients == {}
    assert mod._tenant_client_timestamps == {}
    assert mod._client is None
