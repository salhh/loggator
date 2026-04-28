# Platform Observability — System Events & Audit Log

**Date:** 2026-04-22  
**Status:** Approved  
**Scope:** Loggator API (`loggator-api`) + Loggator Web (`loggator-web`)

---

## Problem

The platform has no visibility into its own behaviour:

1. When the LLM disconnects, a batch fails, or an alert is not delivered, there is no record of what happened or why — only transient structlog output that vanishes with the container.
2. Every API call is invisible: no record of what was called, by whom, with what outcome.

---

## Goals

- Store all meaningful platform activity (operational events + errors) in the database, queryable via API, and visible in the dashboard.
- Store every API request in the database (method, path, status, duration, IP, request ID).
- Show a live "Platform Health" page with a per-service status board and a filterable event feed.
- Actor identity (user / API key) is deferred until the IAM integration is complete — `actor_id` and `actor_type` columns are present but null.

---

## Out of Scope

- IAM / actor identity population
- Log retention / automatic pruning (future background job)
- Request/response body logging
- Per-query OpenSearch or per-DB-query audit events (too noisy)

---

## Data Model

### `system_events` table

Stores platform diagnostic events and operational activity.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `timestamp` | timestamptz | `default now()`, indexed |
| `service` | text | `llm`, `opensearch`, `postgres`, `scheduler`, `alerts`, `streaming` |
| `event_type` | text | See event type catalogue below |
| `severity` | text | `info`, `warning`, `error`, `critical` |
| `message` | text | Human-readable summary |
| `details` | JSONB | Raw error, config, retry count, token estimate, etc. |
| `resolved_at` | timestamptz | Nullable — set when a `reconnected` / `recovered` event closes a prior error |

**Event type catalogue:**

| event_type | severity | Emitted by |
|------------|----------|------------|
| `disconnected` | error | LLM, OpenSearch after retries exhausted |
| `reconnected` | info | LLM, OpenSearch on first success after error |
| `error` | error/critical | Any unhandled exception (scheduler job, streaming worker, DB pool) |
| `recovered` | info | Scheduler job or streaming worker succeeds after prior failure |
| `degraded` | warning | Partial failures (e.g. some chunks fail, others succeed) |
| `batch_started` | info | Batch pipeline begins a run |
| `batch_completed` | info | Batch pipeline finishes successfully |
| `batch_failed` | error | Batch pipeline throws unhandled exception |
| `llm_invoked` | info | A prompt is dispatched to the LLM (batch or streaming) |
| `alert_dispatched` | info / error | Alert sent to Slack, Telegram, email, or webhook (success or failure) |

**De-duplication rule:** Before writing an `error` or `disconnected` event, check whether an identical open event (same `service` + `event_type`, `resolved_at IS NULL`) exists within the last 5 minutes. If so, skip the write. This prevents flooding the table during sustained outages. Operational `info` events (batch runs, alert dispatches) are always written — no de-duplication.

### `audit_log` table

Stores every API request.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `timestamp` | timestamptz | `default now()`, indexed |
| `request_id` | text | UUID generated per-request; echoed in `X-Request-ID` response header |
| `method` | text | HTTP method |
| `path` | text | Request path |
| `status_code` | integer | Response status |
| `duration_ms` | integer | Total request duration |
| `client_ip` | text | From `X-Forwarded-For` (Traefik) or socket |
| `query_params` | JSONB | Sensitive keys (`token`, `api_key`, `password`, `secret`) replaced with `"***"` |
| `error_detail` | text | Exception message if status ≥ 500; null otherwise |
| `actor_id` | text | Null until IAM integration |
| `actor_type` | text | `user`, `api_key` — null until IAM integration |

---

## Architecture

### New backend components

#### `loggator/observability/` (new module)

```
loggator/observability/
    __init__.py
    events.py        # SystemEventWriter — writes system_events rows
    middleware.py    # AuditLogMiddleware — captures every request → audit_log
```

**`SystemEventWriter`** is a plain async class with a single public method:

```python
await system_event_writer.write(
    service="llm",
    event_type="disconnected",
    severity="error",
    message="Ollama unreachable after 3 retries: Connection refused",
    details={"provider": "ollama", "model": "llama3", "error": "...", "retries": 3},
)
```

It handles de-duplication internally. A module-level singleton is imported wherever events need to be emitted.

**`AuditLogMiddleware`** is a Starlette middleware class registered in `main.py`. It:
1. Generates a `request_id` UUID and binds it to the structlog context variable for the duration of the request.
2. Times the request.
3. Catches and re-raises exceptions, capturing the error message if status ≥ 500.
4. Writes the `audit_log` row via `BackgroundTasks` (non-blocking — no latency added to the response).
5. Adds `X-Request-ID: <uuid>` to every response.
6. Skips logging for excluded paths: `/metrics`, `/api/v1/status`, `/api/v1/healthz`, `/api/v1/system-events`, `/api/v1/audit-log`.

#### `loggator/db/models.py` (updated)

Two new SQLAlchemy models: `SystemEvent` and `AuditLog`.

#### Alembic migration

One migration file adds both tables.

### Instrumented call sites

| File | What gets added |
|------|----------------|
| `llm/chain.py` | `write()` on every final failure; `write()` on first success after failure |
| `ollama/client.py` | `write()` after retry exhaustion |
| `pipelines/batch.py` | `write()` at batch_started, llm_invoked (per chunk), batch_completed, batch_failed |
| `pipelines/streaming.py` | `write()` on llm_invoked (per anomaly), worker crash |
| `pipelines/scheduler.py` | `write()` on job exception, job recovery |
| `alerts/dispatcher.py` | `write()` after every channel delivery attempt (success and failure) |
| `opensearch/client.py` | `write()` on connection failure and recovery |
| `db/session.py` | `write()` on pool exhaustion (structlog fallback if DB itself is down) |

### New API endpoints

**`GET /api/v1/system-events`**
- Query params: `service`, `severity`, `event_type`, `from_ts` (default −24 h), `to_ts`, `limit` (default 100, max 500), `offset`
- Response includes a top-level `summary` object (count by service, count by severity) used by the dashboard status board — avoiding a second API call.
- Ordered by `timestamp DESC`.

**`GET /api/v1/system-events/{id}`**
- Full detail including complete `details` JSONB.

**`GET /api/v1/audit-log`**
- Query params: `path` (prefix match), `method`, `status` (exact or prefix e.g. `"5"` → all 5xx), `from_ts` (default −24 h), `to_ts`, `limit` (default 100, max 500), `offset`
- Ordered by `timestamp DESC`.

---

## Frontend

### `/health` page (replaced)

The existing basic health check page is replaced with a two-section layout.

**Status Board (top)**  
Six service cards in a row: `LLM`, `OpenSearch`, `PostgreSQL`, `Scheduler`, `Alerts`, `Streaming`. Each card shows:
- Coloured dot: 🟢 healthy (no open error in last 15 min) / 🟡 degraded (warnings only) / 🔴 error (open unresolved error)
- Service name
- Last event message and relative time ("Connection refused · 3 min ago")

Status is derived from the `summary` in the `GET /api/v1/system-events` response — no extra call needed.

**Tabbed section (bottom)**

*System Events tab* (default):
- Filters: service multi-select, severity multi-select, time range picker
- Event rows: timestamp, severity badge, service tag, message, expandable details panel showing JSONB
- Auto-refreshes every 30 seconds

*Audit Log tab*:
- Filters: path prefix input, method select, status range select (2xx / 3xx / 4xx / 5xx / all)
- Rows: timestamp, method + path, status code (colour-coded), duration ms, client IP
- Manual refresh only (no auto-refresh)

---

## Structlog Integration

`AuditLogMiddleware` binds `request_id` and `client_ip` into the structlog context at request entry. Every `structlog.get_logger()` call inside that request automatically includes these fields. This makes it trivial to correlate structlog terminal output with the `audit_log` row — they share the same `request_id`.

When IAM is integrated, `actor_id` is added to the structlog context in the same middleware, in one place.

---

## Error Handling

- If the DB is unavailable when `SystemEventWriter` tries to write, it falls back to structlog only (no exception propagated to the caller — the event is never lost from logs, just not stored).
- If the DB is unavailable when `AuditLogMiddleware` tries to write (background task), the failure is silently swallowed and logged via structlog — the API response is never affected.
- The `system_events` write for a DB pool exhaustion event uses a fresh short-lived connection attempt rather than the pool, to avoid deadlock.

---

## File Checklist

**New files:**
- `loggator/observability/__init__.py`
- `loggator/observability/events.py`
- `loggator/observability/middleware.py`
- `loggator/api/routes/system_events.py`
- `loggator/api/routes/audit_log.py`
- `alembic/versions/<hash>_add_system_events_and_audit_log.py`
- `loggator-web/src/app/health/page.tsx` (replace existing)
- `loggator-web/src/components/health/StatusBoard.tsx`
- `loggator-web/src/components/health/SystemEventFeed.tsx`
- `loggator-web/src/components/health/AuditLogTable.tsx`
- `loggator-web/src/lib/api/system-events.ts`
- `loggator-web/src/lib/api/audit-log.ts`

**Modified files:**
- `loggator/db/models.py` — add `SystemEvent`, `AuditLog` models
- `loggator/main.py` — register `AuditLogMiddleware`, include new routers
- `loggator/llm/chain.py` — add event writes
- `loggator/ollama/client.py` — add event writes
- `loggator/pipelines/batch.py` — add event writes
- `loggator/pipelines/streaming.py` — add event writes
- `loggator/pipelines/scheduler.py` — add event writes
- `loggator/alerts/dispatcher.py` — add event writes
- `loggator/opensearch/client.py` — add event writes
- `loggator/db/session.py` — add event writes (structlog fallback)
