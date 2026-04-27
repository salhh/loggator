"""
AuditLogMiddleware — records every API request to the audit_log table.

- Generates a request_id UUID and binds it to structlog context.
- Writes the audit_log row asynchronously via BackgroundTask (no added latency).
- Adds X-Request-ID response header.
- Skips excluded paths (metrics, status, healthz, system-events, audit-log).
- Sanitises sensitive query parameters (token, api_key, password, secret).
"""
import time
import uuid
from collections.abc import Awaitable, Callable

import structlog
from starlette.background import BackgroundTask
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from loggator.db.models import AuditLog
from loggator.db.session import AsyncSessionLocal

log = structlog.get_logger()

_SENSITIVE_KEYS = frozenset({"token", "api_key", "password", "secret"})


def _should_skip(path: str) -> bool:
    return path in {"/metrics", "/api/v1/status", "/api/v1/healthz"} or path.startswith(
        ("/api/v1/system-events", "/api/v1/audit-log")
    )


def _sanitize_params(params: dict) -> dict:
    return {
        k: ("***" if k.lower() in _SENSITIVE_KEYS else v) for k, v in params.items()
    }


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def _write_audit_row(
    request_id: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: int,
    client_ip: str,
    query_params: dict | None,
    error_detail: str | None,
) -> None:
    try:
        async with AsyncSessionLocal() as session:
            row = AuditLog(
                request_id=request_id,
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                client_ip=client_ip,
                query_params=query_params if query_params else None,
                error_detail=error_detail,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        log.error("audit_log.write_failed", error=str(exc))


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if _should_skip(request.url.path):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        client_ip = _get_client_ip(request)
        query_params = _sanitize_params(dict(request.query_params))

        # Bind to structlog context so all log lines in this request carry request_id
        structlog.contextvars.bind_contextvars(request_id=request_id, client_ip=client_ip)

        start = time.monotonic()
        status_code = 500
        error_detail: str | None = None

        try:
            try:
                response = await call_next(request)
                status_code = response.status_code
            except Exception as exc:
                error_detail = str(exc)
                duration_ms = int((time.monotonic() - start) * 1000)
                await _write_audit_row(
                    request_id, request.method, request.url.path,
                    status_code, duration_ms, client_ip, query_params, error_detail,
                )
                raise

            duration_ms = int((time.monotonic() - start) * 1000)
            response.headers["X-Request-ID"] = request_id
            response.background = BackgroundTask(
                _write_audit_row,
                request_id, request.method, request.url.path,
                status_code, duration_ms, client_ip, query_params,
                error_detail if status_code >= 500 else None,
            )
            return response
        finally:
            structlog.contextvars.clear_contextvars()
