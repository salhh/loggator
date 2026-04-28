# Platform Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent platform self-monitoring (system events) and API audit logging to Loggator, exposing both via API endpoints and a rebuilt `/health` dashboard page.

**Architecture:** A new `loggator/observability/` module provides a `SystemEventWriter` singleton (de-duplicated async DB writes) and an `AuditLogMiddleware` (Starlette middleware that records every request to a background DB task). Two new PostgreSQL tables (`system_events`, `audit_log`) store the data. Three new API endpoints expose the data. The existing `/health` frontend page is replaced with a status board + tabbed event/audit feed.

**Tech Stack:** SQLAlchemy async, Alembic, FastAPI/Starlette middleware, structlog contextvars, Next.js 16 App Router, Tailwind CSS, shadcn/ui Tabs.

---

## File Map

### New backend files
| File | Responsibility |
|------|---------------|
| `loggator/observability/__init__.py` | Re-exports `system_event_writer` singleton |
| `loggator/observability/events.py` | `SystemEventWriter` — async de-duplicated DB writes |
| `loggator/observability/middleware.py` | `AuditLogMiddleware` — captures every request |
| `loggator/api/routes/system_events.py` | `GET /api/v1/system-events`, `GET /api/v1/system-events/{id}` |
| `loggator/api/routes/audit_log.py` | `GET /api/v1/audit-log` |
| `alembic/versions/e1f2a3b4c5d6_add_system_events_and_audit_log.py` | DB migration |

### Modified backend files
| File | What changes |
|------|-------------|
| `loggator/db/models.py` | Add `SystemEvent`, `AuditLog` models |
| `loggator/main.py` | Register `AuditLogMiddleware`, include two new routers |
| `loggator/llm/chain.py` | Emit `llm_invoked`, `error`, `reconnected` events |
| `loggator/pipelines/batch.py` | Emit `batch_started`, `batch_completed`, `batch_failed`, `llm_invoked` |
| `loggator/pipelines/streaming.py` | Emit `llm_invoked` per anomaly, `error`/`recovered` on crash |
| `loggator/pipelines/scheduler.py` | Emit `error`/`recovered` on job exception/recovery |
| `loggator/alerts/dispatcher.py` | Emit `alert_dispatched` after each channel attempt |
| `loggator/opensearch/client.py` | Emit `disconnected`/`reconnected` on client errors |

### New frontend files
| File | Responsibility |
|------|---------------|
| `components/health/StatusBoard.tsx` | Six service cards with coloured status dots |
| `components/health/SystemEventFeed.tsx` | Filterable event list, auto-refresh 30s |
| `components/health/AuditLogTable.tsx` | Filterable audit log table, manual refresh |

### Modified frontend files
| File | What changes |
|------|-------------|
| `lib/types.ts` | Add `SystemEvent`, `SystemEventsResponse`, `AuditLogEntry` |
| `lib/api.ts` | Add `systemEvents()`, `systemEvent()`, `auditLog()` methods |
| `app/health/HealthClient.tsx` | Replace with two-section layout (status board + tabs) |

---

## Task 1: DB Models + Alembic Migration

**Files:**
- Modify: `loggator-api/loggator/db/models.py`
- Create: `loggator-api/alembic/versions/e1f2a3b4c5d6_add_system_events_and_audit_log.py`

- [ ] **Step 1: Add `SystemEvent` and `AuditLog` models to `loggator/db/models.py`**

Append to the end of the file (after `ScheduledAnalysis`):

```python
class SystemEvent(Base):
    __tablename__ = "system_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    service = Column(Text, nullable=False)   # llm | opensearch | postgres | scheduler | alerts | streaming
    event_type = Column(Text, nullable=False)
    severity = Column(Text, nullable=False)  # info | warning | error | critical
    message = Column(Text, nullable=False)
    details = Column(JSONB, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    request_id = Column(Text, nullable=False)
    method = Column(Text, nullable=False)
    path = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    client_ip = Column(Text, nullable=True)
    query_params = Column(JSONB, nullable=True)
    error_detail = Column(Text, nullable=True)
    actor_id = Column(Text, nullable=True)
    actor_type = Column(Text, nullable=True)
```

- [ ] **Step 2: Write the Alembic migration**

Create `loggator-api/alembic/versions/e1f2a3b4c5d6_add_system_events_and_audit_log.py`:

```python
"""add system_events and audit_log tables

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-04-23
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("service", sa.Text(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_system_events_timestamp", "system_events", ["timestamp"])

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("request_id", sa.Text(), nullable=False),
        sa.Column("method", sa.Text(), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("client_ip", sa.Text(), nullable=True),
        sa.Column(
            "query_params",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_timestamp", table_name="audit_log")
    op.drop_table("audit_log")
    op.drop_index("ix_system_events_timestamp", table_name="system_events")
    op.drop_table("system_events")
```

- [ ] **Step 3: Run the migration to verify it applies cleanly**

```bash
cd loggator-api
alembic upgrade head
```

Expected: `Running upgrade d0e1f2a3b4c5 -> e1f2a3b4c5d6, add system_events and audit_log tables` with no errors.

Verify tables exist:
```bash
psql -U loggator -d loggator -c "\dt system_events audit_log"
```

Expected: both tables listed.

- [ ] **Step 4: Commit**

```bash
git add loggator-api/loggator/db/models.py loggator-api/alembic/versions/e1f2a3b4c5d6_add_system_events_and_audit_log.py
git commit -m "feat: add SystemEvent and AuditLog DB models and migration"
```

---

## Task 2: SystemEventWriter

**Files:**
- Create: `loggator-api/loggator/observability/__init__.py`
- Create: `loggator-api/loggator/observability/events.py`

- [ ] **Step 1: Write `loggator/observability/events.py`**

```python
"""
SystemEventWriter — persists platform diagnostic events to system_events.

De-duplication rule: if an identical (service + event_type, resolved_at IS NULL)
event exists within the last 5 minutes, skip the write. This applies only to
`error` and `disconnected` event types. Info events are always written.
"""
import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select

from loggator.db.models import SystemEvent
from loggator.db.session import AsyncSessionLocal

log = structlog.get_logger()

# Only these event_types are subject to de-duplication
_DEDUP_EVENT_TYPES = frozenset({"error", "disconnected"})


class SystemEventWriter:
    async def write(
        self,
        service: str,
        event_type: str,
        severity: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """
        Persist a platform event. Silently falls back to structlog if the DB is
        unavailable — the event is logged but never raises to the caller.
        """
        try:
            async with AsyncSessionLocal() as session:
                # De-duplication for error/disconnected events only
                if event_type in _DEDUP_EVENT_TYPES:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                    result = await session.execute(
                        select(SystemEvent)
                        .where(
                            and_(
                                SystemEvent.service == service,
                                SystemEvent.event_type == event_type,
                                SystemEvent.resolved_at.is_(None),
                                SystemEvent.timestamp >= cutoff,
                            )
                        )
                        .limit(1)
                    )
                    if result.scalar_one_or_none() is not None:
                        log.debug(
                            "system_event.dedup_skipped",
                            service=service,
                            event_type=event_type,
                        )
                        return

                event = SystemEvent(
                    service=service,
                    event_type=event_type,
                    severity=severity,
                    message=message,
                    details=details,
                )
                session.add(event)
                await session.commit()
                log.debug(
                    "system_event.written",
                    service=service,
                    event_type=event_type,
                    severity=severity,
                )
        except Exception as exc:
            # DB unavailable — fall back to structlog only, never propagate
            log.error(
                "system_event.write_failed",
                service=service,
                event_type=event_type,
                error=str(exc),
            )


# Module-level singleton — import this wherever events need to be emitted
system_event_writer = SystemEventWriter()
```

- [ ] **Step 2: Write `loggator/observability/__init__.py`**

```python
from loggator.observability.events import system_event_writer

__all__ = ["system_event_writer"]
```

- [ ] **Step 3: Write a unit test for `SystemEventWriter`**

Create `loggator-api/tests/observability/test_events.py`:

```python
"""Unit tests for SystemEventWriter de-duplication logic."""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from loggator.observability.events import SystemEventWriter


@pytest.mark.asyncio
async def test_info_event_always_written():
    """info events bypass de-duplication and always write."""
    writer = SystemEventWriter()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="scheduler",
            event_type="batch_started",
            severity="info",
            message="Batch pipeline started",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_error_event_deduplicated_when_open_event_exists():
    """error events are skipped when an identical open event exists within 5 min."""
    writer = SystemEventWriter()

    mock_existing = MagicMock()  # simulates an existing open event row
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_error_event_written_when_no_open_event():
    """error event is written when no matching open event exists."""
    writer = SystemEventWriter()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_db_failure_does_not_propagate():
    """If the DB is unavailable, write() silently falls back to structlog."""
    writer = SystemEventWriter()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB connection refused"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        # Must not raise
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )
```

- [ ] **Step 4: Run the tests**

```bash
cd loggator-api
pytest tests/observability/test_events.py -v
```

Expected: 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add loggator-api/loggator/observability/ loggator-api/tests/observability/
git commit -m "feat: add SystemEventWriter with de-duplication"
```

---

## Task 3: AuditLogMiddleware

**Files:**
- Create: `loggator-api/loggator/observability/middleware.py`

- [ ] **Step 1: Write `loggator/observability/middleware.py`**

```python
"""
AuditLogMiddleware — records every API request to the audit_log table.

- Generates a request_id UUID and binds it to structlog context.
- Writes the audit_log row asynchronously via BackgroundTask (no added latency).
- Adds X-Request-ID response header.
- Skips excluded paths (metrics, status, health, system-events, audit-log).
- Sanitises sensitive query parameters (token, api_key, password, secret).
"""
import asyncio
import time
import uuid

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
                query_params=query_params or None,
                error_detail=error_detail,
            )
            session.add(row)
            await session.commit()
    except Exception as exc:
        log.error("audit_log.write_failed", error=str(exc))


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        if _should_skip(request.url.path):
            return await call_next(request)

        request_id = str(uuid.uuid4())
        client_ip = _get_client_ip(request)
        query_params = _sanitize_params(dict(request.query_params))

        # Bind to structlog context so all log lines in this request carry request_id
        structlog.contextvars.bind_contextvars(request_id=request_id, client_ip=client_ip)

        start = time.monotonic()
        status_code = 500
        error_detail = None

        try:
            response = await call_next(request)
            status_code = response.status_code
        except Exception as exc:
            error_detail = str(exc)
            duration_ms = int((time.monotonic() - start) * 1000)
            structlog.contextvars.clear_contextvars()
            # Fire-and-forget write before re-raising
            asyncio.create_task(
                _write_audit_row(
                    request_id,
                    request.method,
                    request.url.path,
                    status_code,
                    duration_ms,
                    client_ip,
                    query_params,
                    error_detail,
                )
            )
            raise

        duration_ms = int((time.monotonic() - start) * 1000)
        structlog.contextvars.clear_contextvars()

        response.headers["X-Request-ID"] = request_id
        response.background = BackgroundTask(
            _write_audit_row,
            request_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
            client_ip,
            query_params,
            error_detail if status_code >= 500 else None,
        )
        return response
```

- [ ] **Step 2: Write tests for `AuditLogMiddleware`**

Create `loggator-api/tests/observability/test_middleware.py`:

```python
"""Tests for AuditLogMiddleware."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from loggator.observability.middleware import AuditLogMiddleware, _should_skip, _sanitize_params


# ── Unit tests for helpers ────────────────────────────────────────────────────

def test_should_skip_excluded_paths():
    assert _should_skip("/metrics") is True
    assert _should_skip("/api/v1/status") is True
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


# ── Integration tests for middleware behaviour ────────────────────────────────

@pytest.fixture
def app():
    app = FastAPI()
    app.add_middleware(AuditLogMiddleware)

    @app.get("/api/v1/anomalies")
    async def anomalies():
        return {"items": []}

    @app.get("/api/v1/status")
    async def status():
        return {"ok": True}

    return app


@pytest.mark.asyncio
async def test_x_request_id_header_present(app):
    """Every non-excluded response gets an X-Request-ID header."""
    with patch("loggator.observability.middleware.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session_cls.return_value = mock_session

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/anomalies")

    assert "x-request-id" in resp.headers
    assert len(resp.headers["x-request-id"]) == 36  # UUID length


@pytest.mark.asyncio
async def test_excluded_path_no_request_id(app):
    """Excluded paths do not get X-Request-ID and are not logged."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/status")

    assert "x-request-id" not in resp.headers
```

- [ ] **Step 3: Run the tests**

```bash
cd loggator-api
pytest tests/observability/test_middleware.py -v
```

Expected: 5 tests pass.

- [ ] **Step 4: Commit**

```bash
git add loggator-api/loggator/observability/middleware.py loggator-api/tests/observability/test_middleware.py
git commit -m "feat: add AuditLogMiddleware with request_id correlation"
```

---

## Task 4: API Routes + Wire Up in main.py

**Files:**
- Create: `loggator-api/loggator/api/routes/system_events.py`
- Create: `loggator-api/loggator/api/routes/audit_log.py`
- Modify: `loggator-api/loggator/main.py`

- [ ] **Step 1: Write `loggator/api/routes/system_events.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import SystemEvent
from loggator.db.session import get_session

router = APIRouter(tags=["observability"])


def _event_dict(e: SystemEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "timestamp": e.timestamp.isoformat(),
        "service": e.service,
        "event_type": e.event_type,
        "severity": e.severity,
        "message": e.message,
        "details": e.details,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
    }


@router.get("/system-events")
async def list_system_events(
    service: str | None = Query(None),
    severity: str | None = Query(None),
    event_type: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    effective_from = from_ts or (now - timedelta(hours=24))
    effective_to = to_ts or now

    filters: list = [
        SystemEvent.timestamp >= effective_from,
        SystemEvent.timestamp <= effective_to,
    ]
    if service:
        filters.append(SystemEvent.service == service)
    if severity:
        filters.append(SystemEvent.severity == severity)
    if event_type:
        filters.append(SystemEvent.event_type == event_type)

    # Paginated event list
    events_q = (
        select(SystemEvent)
        .where(and_(*filters))
        .order_by(SystemEvent.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    events_result = await session.execute(events_q)
    events = events_result.scalars().all()

    # Summary: count by service and severity for the filtered window
    count_q = (
        select(SystemEvent.service, SystemEvent.severity, func.count())
        .where(and_(*filters))
        .group_by(SystemEvent.service, SystemEvent.severity)
    )
    count_result = await session.execute(count_q)
    by_service: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for svc, sev, cnt in count_result:
        by_service[svc] = by_service.get(svc, 0) + cnt
        by_severity[sev] = by_severity.get(sev, 0) + cnt

    # Open errors (last 15 min, unresolved) — drives status board dots
    cutoff_15 = now - timedelta(minutes=15)
    open_q = (
        select(SystemEvent)
        .where(
            and_(
                SystemEvent.severity.in_(["error", "critical"]),
                SystemEvent.resolved_at.is_(None),
                SystemEvent.timestamp >= cutoff_15,
            )
        )
        .order_by(SystemEvent.timestamp.desc())
    )
    open_result = await session.execute(open_q)
    open_errors = open_result.scalars().all()

    return {
        "summary": {
            "by_service": by_service,
            "by_severity": by_severity,
            "open_errors": [
                {
                    "service": e.service,
                    "event_type": e.event_type,
                    "message": e.message,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in open_errors
            ],
        },
        "events": [_event_dict(e) for e in events],
        "total": len(events),
    }


@router.get("/system-events/{event_id}")
async def get_system_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(SystemEvent).where(SystemEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_dict(event)
```

- [ ] **Step 2: Write `loggator/api/routes/audit_log.py`**

```python
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import AuditLog
from loggator.db.session import get_session

router = APIRouter(tags=["observability"])


def _audit_dict(r: AuditLog) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "timestamp": r.timestamp.isoformat(),
        "request_id": r.request_id,
        "method": r.method,
        "path": r.path,
        "status_code": r.status_code,
        "duration_ms": r.duration_ms,
        "client_ip": r.client_ip,
        "query_params": r.query_params,
        "error_detail": r.error_detail,
        "actor_id": r.actor_id,
        "actor_type": r.actor_type,
    }


@router.get("/audit-log")
async def list_audit_log(
    path: str | None = Query(None, description="Prefix match on request path"),
    method: str | None = Query(None),
    status: str | None = Query(None, description="Exact (e.g. '200') or prefix (e.g. '5' for all 5xx)"),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    effective_from = from_ts or (now - timedelta(hours=24))
    effective_to = to_ts or now

    filters: list = [
        AuditLog.timestamp >= effective_from,
        AuditLog.timestamp <= effective_to,
    ]
    if path:
        filters.append(AuditLog.path.startswith(path))
    if method:
        filters.append(AuditLog.method == method.upper())
    if status:
        if len(status) == 1 and status.isdigit():
            # e.g. "5" → 500–599
            lo = int(status) * 100
            filters.append(
                and_(AuditLog.status_code >= lo, AuditLog.status_code < lo + 100)
            )
        elif status.isdigit():
            filters.append(AuditLog.status_code == int(status))

    q = (
        select(AuditLog)
        .where(and_(*filters))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(q)
    rows = result.scalars().all()
    return [_audit_dict(r) for r in rows]
```

- [ ] **Step 3: Register middleware and routers in `loggator/main.py`**

Add these two imports after the existing route imports:

```python
from loggator.api.routes import system_events as system_events_routes
from loggator.api.routes import audit_log as audit_log_routes
from loggator.observability.middleware import AuditLogMiddleware
```

Register the middleware — add this line **after** the `SlowAPIMiddleware` line:

```python
app.add_middleware(AuditLogMiddleware)
```

Register the routers — add these two lines **after** the `alert_channels_routes` include:

```python
app.include_router(system_events_routes.router, prefix="/api/v1")
app.include_router(audit_log_routes.router, prefix="/api/v1")
```

The final middleware section of `main.py` should look like:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditLogMiddleware)
```

And the router includes (at the bottom) should include:

```python
app.include_router(alert_channels_routes.router, prefix="/api/v1")
app.include_router(system_events_routes.router, prefix="/api/v1")
app.include_router(audit_log_routes.router, prefix="/api/v1")
app.include_router(websocket.router)
```

- [ ] **Step 4: Verify the API starts without errors**

```bash
cd loggator-api
uvicorn loggator.main:app --port 8000 --reload
```

Expected: server starts, no import errors.

In another terminal:
```bash
curl -s http://localhost:8000/api/v1/system-events | python -m json.tool
```

Expected: JSON with `summary`, `events`, `total` keys.

```bash
curl -I http://localhost:8000/api/v1/anomalies
```

Expected: response includes `x-request-id` header.

- [ ] **Step 5: Commit**

```bash
git add loggator-api/loggator/api/routes/system_events.py \
        loggator-api/loggator/api/routes/audit_log.py \
        loggator-api/loggator/main.py
git commit -m "feat: add system-events and audit-log API routes; wire AuditLogMiddleware"
```

---

## Task 5: Instrument Pipelines (batch, streaming, scheduler)

**Files:**
- Modify: `loggator-api/loggator/pipelines/batch.py`
- Modify: `loggator-api/loggator/pipelines/streaming.py`
- Modify: `loggator-api/loggator/pipelines/scheduler.py`

- [ ] **Step 1: Instrument `loggator/pipelines/batch.py`**

Add import at the top (after existing imports):

```python
from loggator.observability import system_event_writer
```

In `run_batch()`, add the following writes at the points indicated:

After the `log.info("batch.start", ...)` line, add:
```python
    await system_event_writer.write(
        service="scheduler",
        event_type="batch_started",
        severity="info",
        message=f"Batch pipeline started for index {index} (window {window}m)",
        details={"index": index, "window_minutes": window, "from_ts": from_ts.isoformat()},
    )
```

Replace the `return None` in the `except` block for OpenSearch failure:
```python
    except Exception as exc:
        log.error("batch.opensearch.failed", error=str(exc))
        await system_event_writer.write(
            service="opensearch",
            event_type="disconnected",
            severity="error",
            message=f"OpenSearch unreachable during batch: {exc}",
            details={"error": str(exc), "index": index},
        )
        return None
```

Replace the `return None` in the `except` block for LLM failure:
```python
    except Exception as exc:
        log.error("batch.llm.failed", error=str(exc))
        await system_event_writer.write(
            service="llm",
            event_type="batch_failed",
            severity="error",
            message=f"Batch pipeline LLM step failed: {exc}",
            details={"error": str(exc), "index": index, "chunks": len(chunks)},
        )
        return None
```

After `log.info("batch.llm.done", ...)`, add the `llm_invoked` event:
```python
    log.info("batch.llm.done", error_count=result.get("error_count", 0))
    await system_event_writer.write(
        service="llm",
        event_type="llm_invoked",
        severity="info",
        message=f"LLM batch summarization complete ({len(chunks)} chunks)",
        details={
            "index": index,
            "chunks": len(chunks),
            "error_count": result.get("error_count", 0),
            "model": _active_model(),
        },
    )
```

After `log.info("batch.saved", ...)`, add the `batch_completed` event:
```python
    log.info("batch.saved", summary_id=str(saved.id), error_count=saved.error_count)
    await system_event_writer.write(
        service="scheduler",
        event_type="batch_completed",
        severity="info",
        message=f"Batch pipeline completed: {saved.error_count} errors found",
        details={
            "summary_id": str(saved.id),
            "index": index,
            "error_count": saved.error_count,
        },
    )
    return saved
```

- [ ] **Step 2: Instrument `loggator/pipelines/streaming.py`**

Add import at the top:

```python
from loggator.observability import system_event_writer
```

In `_process_batch()`, after `await dispatch(anomaly, session)` inside the for loop, add:
```python
        await system_event_writer.write(
            service="streaming",
            event_type="llm_invoked",
            severity="info",
            message=f"Streaming anomaly detected: {severity} in {index_pattern}",
            details={
                "index_pattern": index_pattern,
                "severity": severity,
                "anomaly_id": str(anomaly.id),
            },
        )
```

In `run_streaming_worker()`, replace the `except Exception` block:
```python
        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("streaming.error", error=str(exc))
            await system_event_writer.write(
                service="streaming",
                event_type="error",
                severity="error",
                message=f"Streaming worker error: {exc}",
                details={"error": str(exc), "index_pattern": index_pattern},
            )
```

- [ ] **Step 3: Instrument `loggator/pipelines/scheduler.py`**

Add import at the top:

```python
from loggator.observability import system_event_writer
```

Track prior failure state for batch and analysis jobs using module-level flags. Add after the `_scheduler` declaration:

```python
_batch_last_failed = False
_analysis_last_failed = False
```

Replace `_run_batch_job()` with:
```python
async def _run_batch_job() -> None:
    global _batch_last_failed
    from loggator.pipelines.batch import run_batch
    try:
        summary = await run_batch()
        if summary:
            log.info("scheduler.batch.complete", summary_id=str(summary.id),
                     error_count=summary.error_count)
            if _batch_last_failed:
                await system_event_writer.write(
                    service="scheduler",
                    event_type="recovered",
                    severity="info",
                    message="Batch job recovered after prior failure",
                    details={"summary_id": str(summary.id)},
                )
            _batch_last_failed = False
            from loggator.api.websocket import broadcast
            await broadcast({
                "type": "summary",
                "summary_id": str(summary.id),
                "window_start": summary.window_start.isoformat(),
                "window_end": summary.window_end.isoformat(),
                "error_count": summary.error_count,
                "top_issues": summary.top_issues,
            })
    except Exception as exc:
        log.error("scheduler.batch.error", error=str(exc))
        _batch_last_failed = True
        await system_event_writer.write(
            service="scheduler",
            event_type="error",
            severity="error",
            message=f"Batch scheduler job failed: {exc}",
            details={"error": str(exc)},
        )
```

Replace `_run_analysis_job()` with:
```python
async def _run_analysis_job() -> None:
    global _analysis_last_failed
    from loggator.pipelines.batch import run_scheduled_analysis
    if not settings.analysis_enabled:
        log.info("scheduler.analysis.disabled")
        return
    try:
        record = await run_scheduled_analysis()
        if record:
            log.info("scheduler.analysis.complete", id=str(record.id),
                     error_count=record.error_count, status=record.status)
            if _analysis_last_failed:
                await system_event_writer.write(
                    service="scheduler",
                    event_type="recovered",
                    severity="info",
                    message="Analysis job recovered after prior failure",
                    details={"id": str(record.id)},
                )
            _analysis_last_failed = False
            from loggator.api.websocket import broadcast
            await broadcast({
                "type": "scheduled_analysis",
                "id": str(record.id),
                "window_start": record.window_start.isoformat(),
                "window_end": record.window_end.isoformat(),
                "error_count": record.error_count,
                "status": record.status,
            })
    except Exception as exc:
        log.error("scheduler.analysis.error", error=str(exc))
        _analysis_last_failed = True
        await system_event_writer.write(
            service="scheduler",
            event_type="error",
            severity="error",
            message=f"Analysis scheduler job failed: {exc}",
            details={"error": str(exc)},
        )
```

- [ ] **Step 4: Commit**

```bash
git add loggator-api/loggator/pipelines/batch.py \
        loggator-api/loggator/pipelines/streaming.py \
        loggator-api/loggator/pipelines/scheduler.py
git commit -m "feat: instrument batch, streaming, scheduler pipelines with system events"
```

---

## Task 6: Instrument Services (LLM chain, OpenSearch, alert dispatcher)

**Files:**
- Modify: `loggator-api/loggator/llm/chain.py`
- Modify: `loggator-api/loggator/opensearch/client.py`
- Modify: `loggator-api/loggator/alerts/dispatcher.py`

- [ ] **Step 1: Instrument `loggator/llm/chain.py`**

Add import at the top (after existing imports):

```python
from loggator.observability import system_event_writer
```

Add a `_last_failed` instance variable to `__init__`. After `self._semaphore = asyncio.Semaphore(...)`:
```python
        self._last_failed = False
```

Replace the `generate()` method's except block to emit events:
```python
            try:
                result = await chain.ainvoke({"logs": user_content})
                if self._last_failed:
                    await system_event_writer.write(
                        service="llm",
                        event_type="reconnected",
                        severity="info",
                        message=f"LLM {self._label} recovered after prior failure",
                        details={"provider": self._provider, "label": self._label},
                    )
                self._last_failed = False
            except Exception as exc:
                log.error("llm.generate.failed", provider=self._provider, label=self._label,
                          prompt_type=prompt_type, error=str(exc))
                self._last_failed = True
                await system_event_writer.write(
                    service="llm",
                    event_type="error",
                    severity="error",
                    message=f"LLM {self._label} generate failed: {exc}",
                    details={
                        "provider": self._provider,
                        "label": self._label,
                        "prompt_type": prompt_type,
                        "error": str(exc),
                    },
                )
                raise
            return result.model_dump()
```

Replace the `ainvoke()` method's except block similarly:
```python
            try:
                result = await self._model.ainvoke(messages)
                if self._last_failed:
                    await system_event_writer.write(
                        service="llm",
                        event_type="reconnected",
                        severity="info",
                        message=f"LLM {self._label} recovered after prior failure",
                        details={"provider": self._provider, "label": self._label},
                    )
                self._last_failed = False
            except Exception as exc:
                log.error("llm.ainvoke.failed", provider=self._provider, label=self._label, error=str(exc))
                self._last_failed = True
                await system_event_writer.write(
                    service="llm",
                    event_type="error",
                    severity="error",
                    message=f"LLM {self._label} invocation failed: {exc}",
                    details={
                        "provider": self._provider,
                        "label": self._label,
                        "error": str(exc),
                    },
                )
                raise
            content = result.content
```

- [ ] **Step 2: Instrument `loggator/opensearch/client.py`**

Add import at the top:

```python
from loggator.observability import system_event_writer
```

Add a module-level failure tracker after `_client: AsyncOpenSearch | None = None`:

```python
_last_build_failed = False
```

Replace `get_client()` with a version that emits events on first-time errors and recovery:

```python
def get_client() -> AsyncOpenSearch:
    global _client, _last_build_failed
    if _client is None:
        try:
            _client = _build_client()
            log.info("opensearch.client.created", auth_type=settings.opensearch_auth_type)
            if _last_build_failed:
                import asyncio
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
            import asyncio
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
```

- [ ] **Step 3: Instrument `loggator/alerts/dispatcher.py`**

Add import at the top (after existing imports):

```python
from loggator.observability import system_event_writer
```

In the `_record()` inner async function inside `dispatch()`, add a write after the `session.refresh(alert)` line:

```python
        async def _record(channel: str, destination: str, ok: bool, error: str) -> Alert:
            alert = Alert(
                anomaly_id=anomaly.id,
                channel=channel,
                destination=destination,
                payload=payload,
                status="sent" if ok else "failed",
                error=error if not ok else None,
            )
            session.add(alert)
            await session.commit()
            await session.refresh(alert)
            await system_event_writer.write(
                service="alerts",
                event_type="alert_dispatched",
                severity="info" if ok else "error",
                message=f"Alert {channel} to {destination}: {'sent' if ok else 'failed'}",
                details={
                    "channel": channel,
                    "destination": destination,
                    "ok": ok,
                    "error": error or None,
                    "anomaly_id": str(anomaly.id),
                    "severity": anomaly.severity,
                },
            )
            return alert
```

- [ ] **Step 4: Verify the app still starts cleanly**

```bash
cd loggator-api
uvicorn loggator.main:app --port 8000
```

Expected: no import errors or startup exceptions.

- [ ] **Step 5: Commit**

```bash
git add loggator-api/loggator/llm/chain.py \
        loggator-api/loggator/opensearch/client.py \
        loggator-api/loggator/alerts/dispatcher.py
git commit -m "feat: instrument LLM chain, OpenSearch client, and alert dispatcher with system events"
```

---

## Task 7: Frontend — Types + API Client

**Files:**
- Modify: `loggator-web/lib/types.ts`
- Modify: `loggator-web/lib/api.ts`

- [ ] **Step 1: Add new types to `lib/types.ts`**

Append to the end of the file:

```typescript
// ── Platform Observability ─────────────────────────────────────────────────

export interface SystemEvent {
  id: string;
  timestamp: string;
  service: string;
  event_type: string;
  severity: "info" | "warning" | "error" | "critical";
  message: string;
  details: Record<string, unknown> | null;
  resolved_at: string | null;
}

export interface OpenError {
  service: string;
  event_type: string;
  message: string;
  timestamp: string;
}

export interface SystemEventsResponse {
  summary: {
    by_service: Record<string, number>;
    by_severity: Record<string, number>;
    open_errors: OpenError[];
  };
  events: SystemEvent[];
  total: number;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  request_id: string;
  method: string;
  path: string;
  status_code: number | null;
  duration_ms: number | null;
  client_ip: string | null;
  query_params: Record<string, string> | null;
  error_detail: string | null;
  actor_id: string | null;
  actor_type: string | null;
}
```

- [ ] **Step 2: Add API client methods to `lib/api.ts`**

Add these imports at the top:
```typescript
import type { ..., SystemEventsResponse, SystemEvent, AuditLogEntry } from "./types";
```

(Add `SystemEventsResponse`, `SystemEvent`, `AuditLogEntry` to the existing import list from `"./types"`.)

Add the following methods to the `api` object (before the closing `};`):

```typescript
  systemEvents: (params?: {
    service?: string;
    severity?: string;
    event_type?: string;
    from_ts?: string;
    to_ts?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.service) qs.set("service", params.service);
    if (params?.severity) qs.set("severity", params.severity);
    if (params?.event_type) qs.set("event_type", params.event_type);
    if (params?.from_ts) qs.set("from_ts", params.from_ts);
    if (params?.to_ts) qs.set("to_ts", params.to_ts);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<SystemEventsResponse>(`/system-events${q ? `?${q}` : ""}`);
  },
  systemEvent: (id: string) => get<SystemEvent>(`/system-events/${id}`),
  auditLog: (params?: {
    path?: string;
    method?: string;
    status?: string;
    from_ts?: string;
    to_ts?: string;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.path) qs.set("path", params.path);
    if (params?.method) qs.set("method", params.method);
    if (params?.status) qs.set("status", params.status);
    if (params?.from_ts) qs.set("from_ts", params.from_ts);
    if (params?.to_ts) qs.set("to_ts", params.to_ts);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const q = qs.toString();
    return get<AuditLogEntry[]>(`/audit-log${q ? `?${q}` : ""}`);
  },
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd loggator-web
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no type errors.

- [ ] **Step 4: Commit**

```bash
git add loggator-web/lib/types.ts loggator-web/lib/api.ts
git commit -m "feat: add SystemEvent, AuditLogEntry types and API client methods"
```

---

## Task 8: Frontend — Health Page (StatusBoard + Event Feed + Audit Log)

**Files:**
- Create: `loggator-web/components/health/StatusBoard.tsx`
- Create: `loggator-web/components/health/SystemEventFeed.tsx`
- Create: `loggator-web/components/health/AuditLogTable.tsx`
- Modify: `loggator-web/app/health/HealthClient.tsx`

- [ ] **Step 1: Create `components/health/StatusBoard.tsx`**

```tsx
import type { OpenError, SystemEventsResponse } from "@/lib/types";

const SERVICES = ["llm", "opensearch", "postgres", "scheduler", "alerts", "streaming"] as const;
const SERVICE_LABELS: Record<string, string> = {
  llm: "LLM",
  opensearch: "OpenSearch",
  postgres: "PostgreSQL",
  scheduler: "Scheduler",
  alerts: "Alerts",
  streaming: "Streaming",
};

type Dot = "healthy" | "degraded" | "error";

function getDot(service: string, openErrors: OpenError[]): Dot {
  if (openErrors.some((e) => e.service === service)) return "error";
  return "healthy";
}

function getLastEvent(
  service: string,
  openErrors: OpenError[],
  events: SystemEventsResponse["events"]
) {
  const err = openErrors.find((e) => e.service === service);
  if (err) return { message: err.message, timestamp: err.timestamp };
  const ev = events.find((e) => e.service === service);
  if (ev) return { message: ev.message, timestamp: ev.timestamp };
  return null;
}

function relativeTime(iso: string): string {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

function ServiceCard({
  service,
  dot,
  last,
}: {
  service: string;
  dot: Dot;
  last: { message: string; timestamp: string } | null;
}) {
  const dotColor =
    dot === "error"
      ? "bg-red-400"
      : dot === "degraded"
      ? "bg-amber-400"
      : "bg-emerald-400";
  const borderColor =
    dot === "error"
      ? "border-red-500/40"
      : dot === "degraded"
      ? "border-amber-400/30"
      : "border-border";

  return (
    <div
      className={`bg-card rounded-lg border ${borderColor} p-4 flex flex-col gap-2`}
    >
      <div className="flex items-center gap-2">
        <span className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${dotColor}`} />
        <span className="text-sm font-medium text-foreground">
          {SERVICE_LABELS[service] ?? service}
        </span>
      </div>
      {last ? (
        <p className="text-xs text-muted-foreground leading-relaxed break-words line-clamp-2">
          {last.message}
          <span className="ml-1 text-muted-foreground/60">
            · {relativeTime(last.timestamp)}
          </span>
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">No recent events</p>
      )}
    </div>
  );
}

export default function StatusBoard({ data }: { data: SystemEventsResponse }) {
  const { open_errors } = data.summary;
  const { events } = data;

  return (
    <div>
      <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
        Service Status
      </h2>
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {SERVICES.map((svc) => (
          <ServiceCard
            key={svc}
            service={svc}
            dot={getDot(svc, open_errors)}
            last={getLastEvent(svc, open_errors, events)}
          />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create `components/health/SystemEventFeed.tsx`**

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SystemEvent, SystemEventsResponse } from "@/lib/types";

const SERVICES = ["llm", "opensearch", "postgres", "scheduler", "alerts", "streaming"];
const SEVERITIES = ["info", "warning", "error", "critical"];

const SEVERITY_BADGE: Record<string, string> = {
  info: "bg-sky-400/10 text-sky-400 border border-sky-400/20",
  warning: "bg-amber-400/10 text-amber-400 border border-amber-400/20",
  error: "bg-red-400/10 text-red-400 border border-red-400/20",
  critical: "bg-purple-400/10 text-purple-400 border border-purple-400/20",
};

function EventRow({ event }: { event: SystemEvent }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className="border-b border-border last:border-0 py-2.5 px-1">
      <div
        className="flex items-start gap-3 cursor-pointer"
        onClick={() => setExpanded((v) => !v)}
      >
        <span className="text-xs font-mono text-muted-foreground shrink-0 w-36">
          {new Date(event.timestamp).toLocaleString()}
        </span>
        <span
          className={`text-[11px] font-semibold px-1.5 py-0.5 rounded shrink-0 ${
            SEVERITY_BADGE[event.severity] ?? ""
          }`}
        >
          {event.severity}
        </span>
        <span className="text-xs text-cyan-400 bg-cyan-400/10 px-1.5 py-0.5 rounded shrink-0">
          {event.service}
        </span>
        <span className="text-sm text-foreground leading-snug flex-1 min-w-0">
          {event.message}
        </span>
      </div>
      {expanded && event.details && (
        <pre className="mt-2 ml-4 p-3 bg-secondary rounded text-xs font-mono text-muted-foreground overflow-x-auto whitespace-pre-wrap">
          {JSON.stringify(event.details, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function SystemEventFeed({
  onDataUpdate,
}: {
  onDataUpdate?: (data: SystemEventsResponse) => void;
}) {
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterService, setFilterService] = useState("");
  const [filterSeverity, setFilterSeverity] = useState("");
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = useCallback(async () => {
    try {
      const data = await api.systemEvents({
        service: filterService || undefined,
        severity: filterSeverity || undefined,
        limit: 100,
      });
      setEvents(data.events);
      onDataUpdate?.(data);
    } catch {
      // keep stale data on error
    } finally {
      setLoading(false);
    }
  }, [filterService, filterSeverity, onDataUpdate]);

  useEffect(() => {
    setLoading(true);
    fetch();
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(fetch, 30_000);
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [fetch]);

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <select
          value={filterService}
          onChange={(e) => setFilterService(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All services</option>
          {SERVICES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <select
          value={filterSeverity}
          onChange={(e) => setFilterSeverity(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All severities</option>
          {SEVERITIES.map((s) => (
            <option key={s} value={s}>{s}</option>
          ))}
        </select>
        <span className="text-xs text-muted-foreground self-center ml-auto">
          Auto-refresh every 30s
        </span>
      </div>

      {/* Event list */}
      <div className="bg-card border border-border rounded-lg px-3 py-1">
        {loading && events.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Loading…</div>
        ) : events.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No events in the last 24 hours</div>
        ) : (
          events.map((e) => <EventRow key={e.id} event={e} />)
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Create `components/health/AuditLogTable.tsx`**

```tsx
"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types";

const METHOD_COLOR: Record<string, string> = {
  GET: "text-emerald-400",
  POST: "text-sky-400",
  PUT: "text-amber-400",
  DELETE: "text-red-400",
  PATCH: "text-purple-400",
};

function statusColor(code: number | null): string {
  if (!code) return "text-muted-foreground";
  if (code < 300) return "text-emerald-400";
  if (code < 400) return "text-sky-400";
  if (code < 500) return "text-amber-400";
  return "text-red-400";
}

export default function AuditLogTable() {
  const [rows, setRows] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterPath, setFilterPath] = useState("");
  const [filterMethod, setFilterMethod] = useState("");
  const [filterStatus, setFilterStatus] = useState("");
  const [fetched, setFetched] = useState(false);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.auditLog({
        path: filterPath || undefined,
        method: filterMethod || undefined,
        status: filterStatus || undefined,
        limit: 100,
      });
      setRows(data);
      setFetched(true);
    } catch {
      // keep stale data
    } finally {
      setLoading(false);
    }
  }, [filterPath, filterMethod, filterStatus]);

  return (
    <div className="space-y-3">
      {/* Filters */}
      <div className="flex flex-wrap gap-2">
        <input
          type="text"
          placeholder="/api/v1/..."
          value={filterPath}
          onChange={(e) => setFilterPath(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground placeholder:text-muted-foreground w-44"
        />
        <select
          value={filterMethod}
          onChange={(e) => setFilterMethod(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All methods</option>
          {["GET", "POST", "PUT", "PATCH", "DELETE"].map((m) => (
            <option key={m} value={m}>{m}</option>
          ))}
        </select>
        <select
          value={filterStatus}
          onChange={(e) => setFilterStatus(e.target.value)}
          className="text-xs bg-secondary border border-border rounded px-2 py-1.5 text-foreground"
        >
          <option value="">All statuses</option>
          <option value="2">2xx</option>
          <option value="3">3xx</option>
          <option value="4">4xx</option>
          <option value="5">5xx</option>
        </select>
        <button
          onClick={fetch}
          disabled={loading}
          className="text-xs px-3 py-1.5 rounded border border-border text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Loading…" : "Refresh"}
        </button>
      </div>

      {/* Table */}
      <div className="bg-card border border-border rounded-lg overflow-x-auto">
        {!fetched ? (
          <div className="py-8 text-center text-sm text-muted-foreground">
            Click Refresh to load audit logs
          </div>
        ) : rows.length === 0 ? (
          <div className="py-8 text-center text-sm text-muted-foreground">No entries</div>
        ) : (
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                <th className="text-left px-3 py-2 font-medium">Time</th>
                <th className="text-left px-3 py-2 font-medium">Method · Path</th>
                <th className="text-left px-3 py-2 font-medium">Status</th>
                <th className="text-left px-3 py-2 font-medium">Duration</th>
                <th className="text-left px-3 py-2 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id} className="border-b border-border last:border-0 hover:bg-secondary/40">
                  <td className="px-3 py-2 font-mono text-muted-foreground whitespace-nowrap">
                    {new Date(r.timestamp).toLocaleTimeString()}
                  </td>
                  <td className="px-3 py-2 font-mono">
                    <span className={`${METHOD_COLOR[r.method] ?? ""} mr-1.5`}>{r.method}</span>
                    <span className="text-foreground">{r.path}</span>
                  </td>
                  <td className={`px-3 py-2 font-mono font-semibold ${statusColor(r.status_code)}`}>
                    {r.status_code ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground">
                    {r.duration_ms != null ? `${r.duration_ms}ms` : "—"}
                  </td>
                  <td className="px-3 py-2 text-muted-foreground font-mono">
                    {r.client_ip ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Replace `app/health/HealthClient.tsx`**

Replace the entire file with:

```tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { SystemEventsResponse } from "@/lib/types";
import StatusBoard from "@/components/health/StatusBoard";
import SystemEventFeed from "@/components/health/SystemEventFeed";
import AuditLogTable from "@/components/health/AuditLogTable";

type Tab = "events" | "audit";

export default function HealthClient() {
  const [tab, setTab] = useState<Tab>("events");
  const [data, setData] = useState<SystemEventsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const res = await api.systemEvents({ limit: 50 });
      setData(res);
      setLastChecked(Date.now());
    } catch {
      // keep stale data
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    pollRef.current = setInterval(fetchData, 30_000);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchData]);

  // Elapsed counter
  useEffect(() => {
    const t = setInterval(() => {
      if (lastChecked !== null) setElapsed(Math.floor((Date.now() - lastChecked) / 1000));
    }, 1_000);
    return () => clearInterval(t);
  }, [lastChecked]);

  const tabClass = (t: Tab) =>
    `px-4 py-2 text-sm font-medium transition-colors border-b-2 ${
      tab === t
        ? "border-cyan-400 text-foreground"
        : "border-transparent text-muted-foreground hover:text-foreground"
    }`;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-foreground flex-1">Platform Health</h1>
        {lastChecked !== null && (
          <span className="text-xs text-muted-foreground">Updated {elapsed}s ago</span>
        )}
        <button
          onClick={() => { setLoading(true); fetchData(); }}
          disabled={loading}
          className="px-3 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      {/* Status board skeleton or board */}
      {loading && !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className="bg-card rounded-lg border border-border p-4 animate-pulse h-20" />
          ))}
        </div>
      ) : data ? (
        <StatusBoard data={data} />
      ) : null}

      {/* Tabs */}
      <div>
        <div className="flex border-b border-border mb-4">
          <button className={tabClass("events")} onClick={() => setTab("events")}>
            System Events
          </button>
          <button className={tabClass("audit")} onClick={() => setTab("audit")}>
            Audit Log
          </button>
        </div>

        {tab === "events" && (
          <SystemEventFeed onDataUpdate={(d) => setData(d)} />
        )}
        {tab === "audit" && <AuditLogTable />}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Verify the frontend builds**

```bash
cd loggator-web
npm run build 2>&1 | tail -30
```

Expected: build succeeds, no TypeScript or import errors.

- [ ] **Step 6: Spot-check in browser**

Start dev server:
```bash
cd loggator-web
npm run dev
```

Visit `http://localhost:3000/health`:
- Status board shows 6 service cards (all healthy since no events yet)
- "System Events" tab shows "No events in the last 24 hours"
- "Audit Log" tab shows "Click Refresh to load audit logs"
- Clicking Refresh on Audit Log shows entries (the requests made to load the page itself are in the DB)

- [ ] **Step 7: Commit**

```bash
git add loggator-web/components/health/ \
        loggator-web/app/health/HealthClient.tsx
git commit -m "feat: replace health page with status board + system events + audit log tabs"
```

---

## Self-Review Checklist

Verify the following before marking done:

- [ ] `system_event_writer.write()` never raises — all exceptions are caught internally ✓
- [ ] `AuditLogMiddleware` correctly skips `/api/v1/system-events/*` and `/api/v1/audit-log` ✓
- [ ] Sensitive query param keys (`token`, `api_key`, `password`, `secret`) are redacted to `***` ✓
- [ ] De-duplication only applies to `error` and `disconnected` event types — `info` events always write ✓
- [ ] Migration `down_revision` is `d0e1f2a3b4c5` (the current head) ✓
- [ ] `X-Request-ID` header appears on every non-excluded response ✓
- [ ] Status board reads `open_errors` from the `summary` key — no extra API call ✓
- [ ] System Events tab auto-refreshes every 30s; Audit Log tab is manual-only ✓
- [ ] All six services are represented in the status board (`llm`, `opensearch`, `postgres`, `scheduler`, `alerts`, `streaming`) ✓
- [ ] `actor_id` and `actor_type` columns exist but are always null until IAM integration ✓
