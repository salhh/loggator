# Statistics & Health Status Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `/health` page (live system health for DB, OpenSearch, LLM, scheduler, and alert channels with auto-refresh) and a `/stats` page (aggregate throughput and log-volume charts for the last 7 or 30 days).

**Architecture:** Two new FastAPI routes (`GET /api/v1/health`, `GET /api/v1/stats`) backed by parallel async checks and PostgreSQL/OpenSearch queries respectively. Two new Next.js pages consume them: `/health` is a client component that polls every 10 s; `/stats` is a server component with `<a>`-based period switching.

**Tech Stack:** FastAPI, SQLAlchemy async, httpx, APScheduler, opensearch-py async, Next.js 15 App Router, Recharts, Tailwind CSS.

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `loggator-api/loggator/api/routes/health.py` | Create | 5-check parallel health endpoint |
| `loggator-api/loggator/api/routes/stats.py` | Create | Aggregate stats from PG + OpenSearch |
| `loggator-api/loggator/main.py` | Modify | Register the two new routers |
| `loggator-web/lib/types.ts` | Modify | Add `HealthCheck`, `HealthResponse`, `StatsResponse` + sub-types |
| `loggator-web/lib/api.ts` | Modify | Add `health()` and `stats()` methods |
| `loggator-web/components/DailyActivityChart.tsx` | Create | Recharts AreaChart for daily summaries/anomalies/alerts |
| `loggator-web/components/LogVolumeChart.tsx` | Create | Recharts stacked BarChart for ERROR/WARN/INFO by day |
| `loggator-web/app/health/page.tsx` | Create | Thin server wrapper |
| `loggator-web/app/health/HealthClient.tsx` | Create | Client component with polling + manual refresh |
| `loggator-web/app/stats/page.tsx` | Create | Server-rendered stats dashboard |
| `loggator-web/components/SidebarNav.tsx` | Modify | Add Statistics + Health nav links |

---

## Task 1: Backend health endpoint

**Files:**
- Create: `loggator-api/loggator/api/routes/health.py`

- [ ] **Step 1: Create the health route file**

```python
# loggator-api/loggator/api/routes/health.py
import asyncio
import time
from datetime import datetime, timezone

import httpx
import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from loggator.config import settings
from loggator.db.session import AsyncSessionLocal
from loggator.opensearch.client import get_client
from loggator.pipelines.scheduler import get_scheduler

router = APIRouter(tags=["health"])
log = structlog.get_logger()

_TIMEOUT = 3.0


class CheckResult(BaseModel):
    ok: bool
    latency_ms: int
    detail: str


class HealthResponse(BaseModel):
    checks: dict[str, CheckResult]
    overall: str  # "ok" | "degraded" | "down"


async def _check_database() -> CheckResult:
    t0 = time.monotonic()
    try:
        async def _query():
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))

        await asyncio.wait_for(_query(), timeout=_TIMEOUT)
        return CheckResult(ok=True, latency_ms=int((time.monotonic() - t0) * 1000), detail="PostgreSQL connected")
    except asyncio.TimeoutError:
        return CheckResult(ok=False, latency_ms=int(_TIMEOUT * 1000), detail="timeout")
    except Exception as exc:
        return CheckResult(ok=False, latency_ms=int((time.monotonic() - t0) * 1000), detail=str(exc)[:120])


async def _check_opensearch() -> CheckResult:
    t0 = time.monotonic()
    try:
        async def _query():
            client = get_client()
            health = await client.cluster.health()
            indices = await client.cat.indices(
                index=settings.opensearch_index_pattern, h="index", format="json"
            )
            count = len(indices) if isinstance(indices, list) else 0
            colour = health.get("status", "unknown")
            return count, colour

        count, colour = await asyncio.wait_for(_query(), timeout=_TIMEOUT)
        return CheckResult(
            ok=True,
            latency_ms=int((time.monotonic() - t0) * 1000),
            detail=f"{count} indices, cluster: {colour}",
        )
    except asyncio.TimeoutError:
        return CheckResult(ok=False, latency_ms=int(_TIMEOUT * 1000), detail="timeout")
    except Exception as exc:
        return CheckResult(ok=False, latency_ms=int((time.monotonic() - t0) * 1000), detail=str(exc)[:120])


async def _check_llm() -> CheckResult:
    t0 = time.monotonic()
    try:
        async def _query():
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                r = await client.get(f"{settings.ollama_base_url}/api/tags")
                r.raise_for_status()

        await asyncio.wait_for(_query(), timeout=_TIMEOUT + 0.5)
        return CheckResult(
            ok=True,
            latency_ms=int((time.monotonic() - t0) * 1000),
            detail=f"{settings.ollama_model} @ {settings.ollama_base_url}",
        )
    except asyncio.TimeoutError:
        return CheckResult(ok=False, latency_ms=int(_TIMEOUT * 1000), detail="timeout")
    except Exception as exc:
        return CheckResult(ok=False, latency_ms=int((time.monotonic() - t0) * 1000), detail=str(exc)[:120])


async def _check_scheduler() -> CheckResult:
    try:
        scheduler = get_scheduler()
        if scheduler is None or not scheduler.running:
            return CheckResult(ok=False, latency_ms=0, detail="scheduler not running")
        jobs = scheduler.get_jobs()
        next_fires = [j.next_run_time for j in jobs if j.next_run_time]
        if not next_fires:
            return CheckResult(ok=True, latency_ms=0, detail="running, no scheduled jobs")
        soonest = min(next_fires)
        diff_s = int((soonest - datetime.now(timezone.utc)).total_seconds())
        if diff_s < 0:
            detail = "running now"
        elif diff_s < 60:
            detail = f"next run in {diff_s}s"
        else:
            detail = f"next run in {diff_s // 60}m"
        return CheckResult(ok=True, latency_ms=0, detail=detail)
    except Exception as exc:
        return CheckResult(ok=False, latency_ms=0, detail=str(exc)[:120])


async def _check_alerts() -> CheckResult:
    parts = []
    parts.append("slack ✓" if settings.slack_webhook_url else "slack ✗")
    parts.append(
        "telegram ✓" if (settings.telegram_bot_token and settings.telegram_chat_id) else "telegram ✗"
    )
    parts.append(
        "email ✓" if (settings.smtp_host and settings.alert_email_to) else "email ✗"
    )
    parts.append("webhook ✓" if settings.alert_webhook_url else "webhook ✗")
    configured = sum(1 for p in parts if "✓" in p)
    return CheckResult(ok=configured > 0, latency_ms=0, detail="  ".join(parts))


@router.get("/health", response_model=HealthResponse)
async def get_health():
    db, os_, llm, sched, alerts = await asyncio.gather(
        _check_database(),
        _check_opensearch(),
        _check_llm(),
        _check_scheduler(),
        _check_alerts(),
    )
    checks = {
        "database": db,
        "opensearch": os_,
        "llm": llm,
        "scheduler": sched,
        "alerts": alerts,
    }
    core_ok = db.ok and os_.ok
    all_ok = all(c.ok for c in checks.values())
    overall = "ok" if all_ok else ("degraded" if core_ok else "down")
    return HealthResponse(checks=checks, overall=overall)
```

- [ ] **Step 2: Smoke-test the file parses (no import errors)**

```bash
cd D:/Loggator/loggator-api
python -c "from loggator.api.routes.health import router; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-api/loggator/api/routes/health.py
git commit -m "feat(api): add GET /api/v1/health endpoint with 5-check parallel health"
```

---

## Task 2: Backend stats endpoint

**Files:**
- Create: `loggator-api/loggator/api/routes/stats.py`

- [ ] **Step 1: Create the stats route file**

```python
# loggator-api/loggator/api/routes/stats.py
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session

router = APIRouter(tags=["stats"])
log = structlog.get_logger()


class StatsTotals(BaseModel):
    summaries: int
    anomalies: int
    alerts_sent: int
    alerts_failed: int


class DailyBucket(BaseModel):
    date: str
    summaries: int
    anomalies: int
    alerts: int


class LogVolumeBucket(BaseModel):
    date: str
    error: int
    warn: int
    info: int


class TopService(BaseModel):
    service: str
    error_count: int


class StatsResponse(BaseModel):
    period_days: int
    totals: StatsTotals
    daily: list[DailyBucket]
    anomalies_by_severity: dict[str, int]
    alerts_by_channel: dict[str, int]
    log_volume: list[LogVolumeBucket]
    top_services: list[TopService]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> StatsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── PostgreSQL totals ──────────────────────────────────────────────────────
    total_summaries = (
        await session.execute(
            text("SELECT COUNT(*) FROM summaries WHERE created_at >= :s"), {"s": since}
        )
    ).scalar_one()

    total_anomalies = (
        await session.execute(
            text("SELECT COUNT(*) FROM anomalies WHERE detected_at >= :s"), {"s": since}
        )
    ).scalar_one()

    alerts_sent = (
        await session.execute(
            text("SELECT COUNT(*) FROM alerts WHERE created_at >= :s AND status = 'sent'"),
            {"s": since},
        )
    ).scalar_one()

    alerts_failed = (
        await session.execute(
            text("SELECT COUNT(*) FROM alerts WHERE created_at >= :s AND status = 'failed'"),
            {"s": since},
        )
    ).scalar_one()

    # ── Daily summaries ────────────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM summaries WHERE created_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_summaries: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (detected_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM anomalies WHERE detected_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_anomalies: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM alerts WHERE created_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_alerts: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    daily: list[DailyBucket] = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        daily.append(
            DailyBucket(
                date=d,
                summaries=daily_summaries.get(d, 0),
                anomalies=daily_anomalies.get(d, 0),
                alerts=daily_alerts.get(d, 0),
            )
        )

    # ── Anomalies by severity ──────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT severity, COUNT(*) FROM anomalies WHERE detected_at >= :s GROUP BY severity"
        ),
        {"s": since},
    )
    sev_map: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}
    anomalies_by_severity = {
        "low": sev_map.get("low", 0),
        "medium": sev_map.get("medium", 0),
        "high": sev_map.get("high", 0),
    }

    # ── Alerts by channel ──────────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT channel, COUNT(*) FROM alerts WHERE created_at >= :s GROUP BY channel"
        ),
        {"s": since},
    )
    alerts_by_channel: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    # ── OpenSearch: log volume + top services (graceful degradation) ───────────
    log_volume: list[LogVolumeBucket] = []
    top_services: list[TopService] = []

    try:
        from loggator.opensearch.client import get_client

        os_client = get_client()

        vol_resp = await os_client.search(
            index=settings.opensearch_index_pattern,
            body={
                "size": 0,
                "query": {"range": {"@timestamp": {"gte": since.isoformat()}}},
                "aggs": {
                    "by_day": {
                        "date_histogram": {
                            "field": "@timestamp",
                            "calendar_interval": "day",
                            "format": "yyyy-MM-dd",
                        },
                        "aggs": {
                            "by_level": {
                                "terms": {"field": "level.keyword", "size": 10}
                            }
                        },
                    }
                },
            },
        )
        for bucket in vol_resp["aggregations"]["by_day"]["buckets"]:
            level_counts = {
                b["key"].upper(): b["doc_count"]
                for b in bucket["by_level"]["buckets"]
            }
            log_volume.append(
                LogVolumeBucket(
                    date=bucket["key_as_string"],
                    error=level_counts.get("ERROR", 0),
                    warn=level_counts.get("WARN", level_counts.get("WARNING", 0)),
                    info=level_counts.get("INFO", 0),
                )
            )

        svc_resp = await os_client.search(
            index=settings.opensearch_index_pattern,
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {"range": {"@timestamp": {"gte": since.isoformat()}}},
                            {"term": {"level.keyword": "ERROR"}},
                        ]
                    }
                },
                "aggs": {
                    "by_service": {
                        "terms": {"field": "service.keyword", "size": 10}
                    }
                },
            },
        )
        for bucket in svc_resp["aggregations"]["by_service"]["buckets"]:
            top_services.append(
                TopService(service=bucket["key"], error_count=bucket["doc_count"])
            )
    except Exception as exc:
        log.warning("stats.opensearch.unavailable", error=str(exc))

    return StatsResponse(
        period_days=days,
        totals=StatsTotals(
            summaries=total_summaries,
            anomalies=total_anomalies,
            alerts_sent=alerts_sent,
            alerts_failed=alerts_failed,
        ),
        daily=daily,
        anomalies_by_severity=anomalies_by_severity,
        alerts_by_channel=alerts_by_channel,
        log_volume=log_volume,
        top_services=top_services,
    )
```

- [ ] **Step 2: Smoke-test the file parses**

```bash
cd D:/Loggator/loggator-api
python -c "from loggator.api.routes.stats import router; print('OK')"
```

Expected output: `OK`

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-api/loggator/api/routes/stats.py
git commit -m "feat(api): add GET /api/v1/stats endpoint with PG + OpenSearch aggregations"
```

---

## Task 3: Register new routes in main.py

**Files:**
- Modify: `loggator-api/loggator/main.py`

- [ ] **Step 1: Add the two new router imports and `include_router` calls**

Open `loggator-api/loggator/main.py`. Find the existing import block:

```python
from loggator.api.routes import summaries, anomalies, alerts, status, chat, logs
from loggator.api.routes import settings as settings_routes
from loggator.api.routes import schedule as schedule_routes
from loggator.api.routes import analysis_reports as analysis_reports_routes
```

Replace it with:

```python
from loggator.api.routes import summaries, anomalies, alerts, status, chat, logs
from loggator.api.routes import settings as settings_routes
from loggator.api.routes import schedule as schedule_routes
from loggator.api.routes import analysis_reports as analysis_reports_routes
from loggator.api.routes import health as health_routes
from loggator.api.routes import stats as stats_routes
```

Then find the block that registers routers:

```python
app.include_router(status.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(schedule_routes.router, prefix="/api/v1")
app.include_router(analysis_reports_routes.router, prefix="/api/v1")
app.include_router(websocket.router)
```

Replace it with:

```python
app.include_router(status.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(schedule_routes.router, prefix="/api/v1")
app.include_router(analysis_reports_routes.router, prefix="/api/v1")
app.include_router(health_routes.router, prefix="/api/v1")
app.include_router(stats_routes.router, prefix="/api/v1")
app.include_router(websocket.router)
```

- [ ] **Step 2: Verify the app loads**

```bash
cd D:/Loggator/loggator-api
python -c "from loggator.main import app; print('OK', len(app.routes), 'routes')"
```

Expected output: `OK` followed by a number greater than the previous count (was ~18, now ~20+).

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-api/loggator/main.py
git commit -m "feat(api): register /health and /stats routers"
```

---

## Task 4: Frontend TypeScript types

**Files:**
- Modify: `loggator-web/lib/types.ts`

- [ ] **Step 1: Append new interfaces to the end of `loggator-web/lib/types.ts`**

Add after the last existing interface:

```typescript
export interface HealthCheck {
  ok: boolean;
  latency_ms: number;
  detail: string;
}

export interface HealthResponse {
  checks: Record<string, HealthCheck>;
  overall: "ok" | "degraded" | "down";
}

export interface StatsDaily {
  date: string;
  summaries: number;
  anomalies: number;
  alerts: number;
}

export interface StatsLogVolume {
  date: string;
  error: number;
  warn: number;
  info: number;
}

export interface StatsTopService {
  service: string;
  error_count: number;
}

export interface StatsResponse {
  period_days: number;
  totals: {
    summaries: number;
    anomalies: number;
    alerts_sent: number;
    alerts_failed: number;
  };
  daily: StatsDaily[];
  anomalies_by_severity: { low: number; medium: number; high: number };
  alerts_by_channel: Record<string, number>;
  log_volume: StatsLogVolume[];
  top_services: StatsTopService[];
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors related to `types.ts`.

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-web/lib/types.ts
git commit -m "feat(web): add HealthResponse and StatsResponse TypeScript types"
```

---

## Task 5: Frontend API client methods

**Files:**
- Modify: `loggator-web/lib/api.ts`

- [ ] **Step 1: Add the import and two new methods**

Open `loggator-web/lib/api.ts`. Find the import line at the top:

```typescript
import type { Summary, Anomaly, Alert, StatusResponse, AnalysisReport, ScheduledAnalysis, ScheduleStatus } from "./types";
```

Replace it with:

```typescript
import type { Summary, Anomaly, Alert, StatusResponse, AnalysisReport, ScheduledAnalysis, ScheduleStatus, HealthResponse, StatsResponse } from "./types";
```

Then find the last entry in the `api` object (currently `analysisReport`):

```typescript
  analysisReport: (id: string) =>
    get<ScheduledAnalysis>(`/analysis-reports/${id}`),
```

Add two new methods after it, before the closing `};`:

```typescript
  health: () =>
    get<HealthResponse>("/health"),
  stats: (days = 7) =>
    get<StatsResponse>(`/stats?days=${days}`),
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-web/lib/api.ts
git commit -m "feat(web): add health() and stats() API client methods"
```

---

## Task 6: Chart components

**Files:**
- Create: `loggator-web/components/DailyActivityChart.tsx`
- Create: `loggator-web/components/LogVolumeChart.tsx`

- [ ] **Step 1: Create `DailyActivityChart.tsx`**

```typescript
// loggator-web/components/DailyActivityChart.tsx
"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { StatsDaily } from "@/lib/types";

export default function DailyActivityChart({ data }: { data: StatsDaily[] }) {
  const formatted = data.map((d) => ({ ...d, date: d.date.slice(5) })); // "YYYY-MM-DD" → "MM-DD"
  return (
    <ResponsiveContainer width="100%" height={180}>
      <AreaChart data={formatted} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <defs>
          <linearGradient id="gSummaries" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#22d3ee" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#22d3ee" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAnomalies" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fbbf24" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fbbf24" stopOpacity={0} />
          </linearGradient>
          <linearGradient id="gAlerts" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#fb7185" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#fb7185" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="date"
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          itemStyle={{ color: "#f3f4f6", padding: "1px 0" }}
          cursor={{ stroke: "#374151", strokeWidth: 1 }}
        />
        <Area type="monotone" dataKey="summaries" stroke="#22d3ee" strokeWidth={1.5} fill="url(#gSummaries)" dot={false} name="Summaries" />
        <Area type="monotone" dataKey="anomalies" stroke="#fbbf24" strokeWidth={1.5} fill="url(#gAnomalies)" dot={false} name="Anomalies" />
        <Area type="monotone" dataKey="alerts" stroke="#fb7185" strokeWidth={1.5} fill="url(#gAlerts)" dot={false} name="Alerts" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 2: Create `LogVolumeChart.tsx`**

```typescript
// loggator-web/components/LogVolumeChart.tsx
"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import type { StatsLogVolume } from "@/lib/types";

export default function LogVolumeChart({ data }: { data: StatsLogVolume[] }) {
  const formatted = data.map((d) => ({ ...d, date: d.date.slice(5) })); // "YYYY-MM-DD" → "MM-DD"
  return (
    <ResponsiveContainer width="100%" height={180}>
      <BarChart data={formatted} margin={{ top: 4, right: 4, left: -20, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
        <XAxis
          dataKey="date"
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          stroke="transparent"
          tick={{ fill: "#4b5563", fontSize: 10 }}
          tickLine={false}
          axisLine={false}
          allowDecimals={false}
        />
        <Tooltip
          contentStyle={{ background: "#111827", border: "1px solid #1f2937", borderRadius: 6, fontSize: 12 }}
          labelStyle={{ color: "#9ca3af", marginBottom: 4 }}
          itemStyle={{ color: "#f3f4f6", padding: "1px 0" }}
          cursor={{ fill: "#1f2937" }}
        />
        <Bar dataKey="error" stackId="a" fill="#f87171" name="Error" />
        <Bar dataKey="warn" stackId="a" fill="#fbbf24" name="Warn" />
        <Bar dataKey="info" stackId="a" fill="#94a3b8" name="Info" radius={[2, 2, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd D:/Loggator
git add loggator-web/components/DailyActivityChart.tsx loggator-web/components/LogVolumeChart.tsx
git commit -m "feat(web): add DailyActivityChart and LogVolumeChart Recharts components"
```

---

## Task 7: Health page (frontend)

**Files:**
- Create: `loggator-web/app/health/page.tsx`
- Create: `loggator-web/app/health/HealthClient.tsx`

- [ ] **Step 1: Create the thin server wrapper `page.tsx`**

```typescript
// loggator-web/app/health/page.tsx
import HealthClient from "./HealthClient";

export default function HealthPage() {
  return <HealthClient />;
}
```

- [ ] **Step 2: Create `HealthClient.tsx`**

```typescript
// loggator-web/app/health/HealthClient.tsx
"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { HealthCheck, HealthResponse } from "@/lib/types";

const SERVICE_LABELS: Record<string, string> = {
  database: "Database",
  opensearch: "OpenSearch",
  llm: "LLM",
  scheduler: "Scheduler",
  alerts: "Alert Channels",
};

const SERVICE_ORDER = ["database", "opensearch", "llm", "scheduler", "alerts"];

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      className={`inline-block w-2.5 h-2.5 rounded-full shrink-0 ${
        ok ? "bg-emerald-400" : "bg-red-400"
      }`}
    />
  );
}

function OverallBadge({ overall }: { overall: "ok" | "degraded" | "down" }) {
  const styles: Record<string, string> = {
    ok: "bg-emerald-400/10 text-emerald-400 border-emerald-400/30",
    degraded: "bg-amber-400/10 text-amber-400 border-amber-400/30",
    down: "bg-red-400/10 text-red-400 border-red-400/30",
  };
  const labels: Record<string, string> = {
    ok: "All Systems OK",
    degraded: "Degraded",
    down: "Down",
  };
  return (
    <span
      className={`px-2.5 py-1 rounded-md border text-xs font-semibold uppercase tracking-wide ${styles[overall]}`}
    >
      {labels[overall]}
    </span>
  );
}

function CheckCard({ name, check }: { name: string; check: HealthCheck }) {
  return (
    <div
      className={`bg-card rounded-lg border p-4 flex flex-col gap-2 ${
        check.ok ? "border-border" : "border-red-500/40"
      }`}
    >
      <div className="flex items-center gap-2">
        <StatusDot ok={check.ok} />
        <span className="text-sm font-medium text-foreground">
          {SERVICE_LABELS[name] ?? name}
        </span>
      </div>
      {check.latency_ms > 0 && (
        <span className="text-xs font-mono text-muted-foreground bg-secondary px-1.5 py-0.5 rounded self-start">
          {check.latency_ms} ms
        </span>
      )}
      <p className="text-xs text-muted-foreground leading-relaxed break-words">
        {check.detail}
      </p>
    </div>
  );
}

export default function HealthClient() {
  const [data, setData] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastChecked, setLastChecked] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchHealth = useCallback(async () => {
    try {
      const res = await api.health();
      setData(res);
      setLastChecked(Date.now());
    } catch {
      // keep stale data on error
    } finally {
      setLoading(false);
    }
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(fetchHealth, 10_000);
  }, [fetchHealth]);

  const handleRefresh = useCallback(() => {
    setLoading(true);
    fetchHealth();
    startPolling();
  }, [fetchHealth, startPolling]);

  // Initial fetch + start polling
  useEffect(() => {
    fetchHealth();
    startPolling();
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [fetchHealth, startPolling]);

  // "Last checked X s ago" counter
  useEffect(() => {
    const t = setInterval(() => {
      if (lastChecked !== null) {
        setElapsed(Math.floor((Date.now() - lastChecked) / 1000));
      }
    }, 1_000);
    return () => clearInterval(t);
  }, [lastChecked]);

  const orderedChecks = data
    ? SERVICE_ORDER.filter((k) => k in data.checks).map((k) => ({
        name: k,
        check: data.checks[k],
      }))
    : [];

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold text-foreground flex-1">System Health</h1>
        {data && <OverallBadge overall={data.overall} />}
        {lastChecked !== null && (
          <span className="text-xs text-muted-foreground">
            Last checked {elapsed}s ago
          </span>
        )}
        <button
          onClick={handleRefresh}
          disabled={loading}
          className="px-3 py-1.5 rounded border border-border text-xs text-muted-foreground hover:text-foreground hover:border-cyan-400 transition-colors disabled:opacity-40"
        >
          {loading ? "Checking…" : "Refresh"}
        </button>
      </div>

      {/* Cards — skeleton while loading before first data */}
      {loading && !data ? (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {SERVICE_ORDER.map((k) => (
            <div
              key={k}
              className="bg-card rounded-lg border border-border p-4 animate-pulse h-28"
            />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3">
          {orderedChecks.map(({ name, check }) => (
            <CheckCard key={name} name={name} check={check} />
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 4: Commit**

```bash
cd D:/Loggator
git add loggator-web/app/health/page.tsx loggator-web/app/health/HealthClient.tsx
git commit -m "feat(web): add /health page with auto-refresh and manual override"
```

---

## Task 8: Stats page (frontend)

**Files:**
- Create: `loggator-web/app/stats/page.tsx`

- [ ] **Step 1: Create `loggator-web/app/stats/page.tsx`**

```typescript
// loggator-web/app/stats/page.tsx
import { api } from "@/lib/api";
import type { StatsResponse } from "@/lib/types";
import StatCard from "@/components/StatCard";
import DailyActivityChart from "@/components/DailyActivityChart";
import LogVolumeChart from "@/components/LogVolumeChart";

const DAYS_OPTIONS = [7, 30] as const;

export default async function StatsPage({
  searchParams,
}: {
  searchParams: Promise<{ days?: string }>;
}) {
  const { days: rawDays } = await searchParams;
  const days: 7 | 30 = DAYS_OPTIONS.includes(Number(rawDays) as 7 | 30)
    ? (Number(rawDays) as 7 | 30)
    : 7;

  let stats: StatsResponse | null = null;
  try {
    stats = await api.stats(days);
  } catch {
    // API offline
  }

  if (!stats) {
    return (
      <div className="space-y-5">
        <h1 className="text-lg font-semibold">Statistics</h1>
        <p className="text-sm text-muted-foreground">
          Could not load statistics — is the API running?
        </p>
      </div>
    );
  }

  const maxErrors = Math.max(...stats.top_services.map((s) => s.error_count), 1);

  return (
    <div className="space-y-6">
      {/* Header + period toggle */}
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-semibold flex-1">Statistics</h1>
        <div className="flex gap-1.5">
          {DAYS_OPTIONS.map((d) => (
            <a
              key={d}
              href={`/stats?days=${d}`}
              className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
                days === d
                  ? "bg-cyan-400 text-black"
                  : "bg-card border border-border text-muted-foreground hover:text-foreground hover:border-cyan-400/60"
              }`}
            >
              {d}d
            </a>
          ))}
        </div>
      </div>

      {/* Row 1: stat cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <StatCard
          label="Summaries"
          value={stats.totals.summaries}
          borderColor="border-l-cyan-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Anomalies"
          value={stats.totals.anomalies}
          borderColor="border-l-amber-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Alerts Sent"
          value={stats.totals.alerts_sent}
          borderColor="border-l-emerald-400"
          sub={`last ${days} days`}
        />
        <StatCard
          label="Alerts Failed"
          value={stats.totals.alerts_failed}
          borderColor="border-l-red-400"
          sub={`last ${days} days`}
        />
      </div>

      {/* Row 2: daily activity chart */}
      <div className="bg-card rounded-lg border border-border p-4">
        <div className="flex items-center gap-4 mb-3 flex-wrap">
          <span className="text-sm font-medium">Daily Activity</span>
          <div className="flex gap-4 ml-auto text-xs text-muted-foreground flex-wrap">
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400 inline-block" />
              Summaries
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
              Anomalies
            </span>
            <span className="flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-400 inline-block" />
              Alerts
            </span>
          </div>
        </div>
        <DailyActivityChart data={stats.daily} />
      </div>

      {/* Row 3: log volume + top error services */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Log volume */}
        <div className="bg-card rounded-lg border border-border p-4">
          <div className="flex items-center gap-4 mb-3 flex-wrap">
            <span className="text-sm font-medium">Log Volume by Day</span>
            <div className="flex gap-4 ml-auto text-xs text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-red-400 inline-block" />
                Error
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-amber-400 inline-block" />
                Warn
              </span>
              <span className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
                Info
              </span>
            </div>
          </div>
          {stats.log_volume.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              Log data unavailable
            </p>
          ) : (
            <LogVolumeChart data={stats.log_volume} />
          )}
        </div>

        {/* Top error services */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Top Error Services</span>
          {stats.top_services.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">No error data</p>
          ) : (
            <div className="space-y-3">
              {stats.top_services.map((s) => (
                <div key={s.service} className="flex items-center gap-3">
                  <span className="text-xs font-mono text-muted-foreground w-36 shrink-0 truncate">
                    {s.service}
                  </span>
                  <div className="flex-1 bg-secondary rounded-full h-1.5">
                    <div
                      className="bg-red-400 h-1.5 rounded-full transition-all"
                      style={{ width: `${(s.error_count / maxErrors) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs font-mono text-muted-foreground w-8 text-right shrink-0">
                    {s.error_count}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Row 4: anomalies by severity + alerts by channel */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Anomalies by severity */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Anomalies by Severity</span>
          <div className="flex gap-3 flex-wrap">
            <span className="px-3 py-1.5 rounded-md bg-emerald-400/10 text-emerald-400 text-sm font-medium border border-emerald-400/20">
              Low — {stats.anomalies_by_severity.low}
            </span>
            <span className="px-3 py-1.5 rounded-md bg-amber-400/10 text-amber-400 text-sm font-medium border border-amber-400/20">
              Medium — {stats.anomalies_by_severity.medium}
            </span>
            <span className="px-3 py-1.5 rounded-md bg-red-400/10 text-red-400 text-sm font-medium border border-red-400/20">
              High — {stats.anomalies_by_severity.high}
            </span>
          </div>
        </div>

        {/* Alerts by channel */}
        <div className="bg-card rounded-lg border border-border p-4">
          <span className="text-sm font-medium block mb-3">Alerts by Channel</span>
          <div className="flex gap-3 flex-wrap">
            {Object.entries(stats.alerts_by_channel).length === 0 ? (
              <p className="text-sm text-muted-foreground">No alerts dispatched yet</p>
            ) : (
              Object.entries(stats.alerts_by_channel).map(([ch, count]) => (
                <span
                  key={ch}
                  className="px-3 py-1.5 rounded-md bg-secondary text-foreground text-sm font-medium border border-border capitalize"
                >
                  {ch} — {count}
                </span>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-web/app/stats/page.tsx
git commit -m "feat(web): add /stats server-component page with charts and period toggle"
```

---

## Task 9: Update sidebar navigation

**Files:**
- Modify: `loggator-web/components/SidebarNav.tsx`

- [ ] **Step 1: Add Statistics and Health to the nav array**

Open `loggator-web/components/SidebarNav.tsx`. Find the `nav` array:

```typescript
const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/logs", label: "Logs" },
  { href: "/summaries", label: "Summaries" },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/alerts", label: "Alerts" },
  { href: "/reports", label: "Reports" },
  { href: "/chat", label: "Chat" },
  { href: "/settings", label: "Settings" },
];
```

Replace it with:

```typescript
const nav = [
  { href: "/", label: "Dashboard" },
  { href: "/logs", label: "Logs" },
  { href: "/summaries", label: "Summaries" },
  { href: "/anomalies", label: "Anomalies" },
  { href: "/alerts", label: "Alerts" },
  { href: "/reports", label: "Reports" },
  { href: "/stats", label: "Statistics" },
  { href: "/health", label: "Health" },
  { href: "/chat", label: "Chat" },
  { href: "/settings", label: "Settings" },
];
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd D:/Loggator/loggator-web
npx tsc --noEmit 2>&1 | head -20
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
cd D:/Loggator
git add loggator-web/components/SidebarNav.tsx
git commit -m "feat(web): add Statistics and Health links to sidebar navigation"
```

---

## Task 10: End-to-end verification

- [ ] **Step 1: Restart the API and verify both new endpoints respond**

```bash
# In D:/Loggator — restart docker or uvicorn, then:
curl -s http://localhost:8000/api/v1/health | python -m json.tool | head -30
```

Expected: JSON with `checks` object containing `database`, `opensearch`, `llm`, `scheduler`, `alerts` keys and an `overall` field.

```bash
curl -s "http://localhost:8000/api/v1/stats?days=7" | python -m json.tool | head -20
```

Expected: JSON with `period_days: 7`, `totals`, `daily` array of 7 entries, `anomalies_by_severity`, etc.

- [ ] **Step 2: Visit `/health` in the browser**

Navigate to `http://localhost:3000/health`. Verify:
- 5 cards render (Database, OpenSearch, LLM, Scheduler, Alert Channels)
- Overall status badge appears
- "Last checked 0s ago" increments each second
- "Refresh" button triggers an immediate re-fetch

- [ ] **Step 3: Visit `/stats` in the browser**

Navigate to `http://localhost:3000/stats`. Verify:
- 4 stat cards show numbers (may be 0 if no data yet)
- Daily activity area chart renders
- "7d" tab is active; clicking "30d" navigates to `?days=30` and shows 30-day data
- Log volume chart and top services panel render (or show placeholders if OpenSearch has no data)

- [ ] **Step 4: Check sidebar**

Verify "Statistics" and "Health" links appear in the sidebar between Reports and Chat, and highlight correctly when active.

- [ ] **Step 5: Final commit if any tweaks were needed**

```bash
cd D:/Loggator
git add -p  # stage only intentional changes
git commit -m "fix: verification tweaks for stats and health pages"
```
