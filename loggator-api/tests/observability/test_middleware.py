"""Tests for AuditLogMiddleware."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from loggator.observability.middleware import (
    AuditLogMiddleware,
    _should_skip,
    _sanitize_params,
)


# ── Unit tests for pure helpers ───────────────────────────────────────────────

def test_should_skip_excluded_paths():
    assert _should_skip("/metrics") is True
    assert _should_skip("/api/v1/status") is True
    assert _should_skip("/api/v1/healthz") is True
    assert _should_skip("/api/v1/system-events") is True
    assert _should_skip("/api/v1/system-events/some-id") is True
    assert _should_skip("/api/v1/audit-log") is True


def test_should_skip_normal_paths():
    assert _should_skip("/api/v1/anomalies") is False
    assert _should_skip("/api/v1/summaries") is False
    assert _should_skip("/api/v1/health") is False


def test_sanitize_params_redacts_sensitive_keys():
    params = {"limit": "10", "token": "secret123", "api_key": "abc", "offset": "0"}
    result = _sanitize_params(params)
    assert result["token"] == "***"
    assert result["api_key"] == "***"
    assert result["limit"] == "10"
    assert result["offset"] == "0"


def test_sanitize_params_case_insensitive():
    params = {"TOKEN": "secret", "Password": "pass"}
    result = _sanitize_params(params)
    assert result["TOKEN"] == "***"
    assert result["Password"] == "***"


# ── Integration tests via ASGI transport ─────────────────────────────────────

@pytest.fixture
def app():
    _app = FastAPI()
    _app.add_middleware(AuditLogMiddleware)

    @_app.get("/api/v1/anomalies")
    async def anomalies():
        return {"items": []}

    @_app.get("/api/v1/status")
    async def status():
        return {"ok": True}

    return _app


@pytest.mark.asyncio
async def test_x_request_id_header_present(app):
    """Every non-excluded response gets an X-Request-ID header."""
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()

    with patch("loggator.observability.middleware.AsyncSessionLocal", return_value=mock_session):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/anomalies")

    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 36  # UUID format


@pytest.mark.asyncio
async def test_excluded_path_no_request_id(app):
    """Excluded paths do not get X-Request-ID."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status")

    assert "x-request-id" not in resp.headers


@pytest.mark.asyncio
async def test_sensitive_query_params_redacted(app):
    """Sensitive params in query string are redacted before writing to audit_log."""
    written_rows = []

    async def fake_write(request_id, method, path, status_code, duration_ms, client_ip, query_params, error_detail):
        written_rows.append(query_params)

    with patch("loggator.observability.middleware._write_audit_row", side_effect=fake_write):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/anomalies?token=supersecret&limit=10")

    assert "x-request-id" in resp.headers
    assert len(written_rows) == 1
    assert written_rows[0]["token"] == "***"
    assert written_rows[0]["limit"] == "10"
