# Statistics & Health Status Pages — Design Spec

## Overview

Add two new pages to Loggator:

1. **`/stats`** — Aggregate metrics about system throughput (summaries, anomalies, alerts) and log volume/error rates by service.
2. **`/health`** — Full system health dashboard showing live connection status for LLM, OpenSearch, PostgreSQL, the background scheduler, and configured alert channels. Auto-refreshes every 10 seconds with a manual override button.

---

## Backend

### New file: `loggator-api/loggator/api/routes/health.py`

**Endpoint:** `GET /api/v1/health`

Runs 5 checks **in parallel** via `asyncio.gather`. Each check has an individual 3-second timeout. Returns within ~3 seconds regardless of which services are slow.

**Response schema:**
```json
{
  "checks": {
    "database":   { "ok": true,  "latency_ms": 4,   "detail": "PostgreSQL connected" },
    "opensearch": { "ok": true,  "latency_ms": 12,  "detail": "3 indices, cluster: green" },
    "llm":        { "ok": true,  "latency_ms": 180, "detail": "llama3 @ http://localhost:11434" },
    "scheduler":  { "ok": true,  "latency_ms": 0,   "detail": "next run in 8 min" },
    "alerts":     { "ok": true,  "latency_ms": 0,   "detail": "slack ✓  telegram ✓  email ✗  webhook ✗" }
  },
  "overall": "ok"
}
```

**`overall` logic:**
- `"ok"` — all 5 checks pass
- `"degraded"` — ≥1 check fails, but database AND opensearch both pass
- `"down"` — database OR opensearch fails

**Individual checks:**

| Check | Method | Detail |
|-------|--------|--------|
| `database` | `SELECT 1` via SQLAlchemy async session | Records latency; catches any exception |
| `opensearch` | `client.cluster.health()` | Reports cluster colour + index count from `cat.indices()` |
| `llm` | `GET {ollama_base_url}/api/tags` via httpx | Records latency; reports model name from config |
| `scheduler` | Read APScheduler next fire time from running instance | No HTTP call; latency always 0 |
| `alerts` | Config inspection only — no actual ping | Reports which channels have credentials set |

If any check times out (>3s): `ok: false, detail: "timeout"`.

---

### New file: `loggator-api/loggator/api/routes/stats.py`

**Endpoint:** `GET /api/v1/stats?days=7`

- `days` query param: integer, default 7, max 30.
- PostgreSQL data (totals, daily, by-severity, by-channel) always returned.
- OpenSearch data (log_volume, top_services) returned as empty arrays if OpenSearch is unreachable — graceful degradation, no 500.

**Response schema:**
```json
{
  "period_days": 7,
  "totals": {
    "summaries": 42,
    "anomalies": 18,
    "alerts_sent": 11,
    "alerts_failed": 2
  },
  "daily": [
    { "date": "2026-04-15", "summaries": 6, "anomalies": 3, "alerts": 2 }
  ],
  "anomalies_by_severity": { "low": 5, "medium": 8, "high": 5 },
  "alerts_by_channel": { "slack": 7, "telegram": 4, "email": 2 },
  "log_volume": [
    { "date": "2026-04-15", "error": 120, "warn": 340, "info": 1800 }
  ],
  "top_services": [
    { "service": "payment-service", "error_count": 88 },
    { "service": "auth-service",    "error_count": 62 }
  ]
}
```

**Data sources:**
- `totals`, `daily`, `anomalies_by_severity`, `alerts_by_channel` — PostgreSQL `SELECT … WHERE created_at >= now() - interval` queries
- `log_volume` — OpenSearch date-histogram aggregation on `@timestamp` field grouped by `level` keyword, over the `logs-*` index pattern
- `top_services` — OpenSearch terms aggregation on `service` keyword filtered to `level: ERROR`

---

### Modifications to existing files

**`loggator-api/loggator/main.py`** — register both new routers:
```python
from loggator.api.routes import health, stats
app.include_router(health.router, prefix="/api/v1")
app.include_router(stats.router, prefix="/api/v1")
```

**`loggator-web/lib/api.ts`** — add two new methods:
```typescript
health: () => get<HealthResponse>("/health"),
stats: (days = 7) => get<StatsResponse>(`/stats?days=${days}`),
```

**`loggator-web/lib/types.ts`** — add two new interfaces:
```typescript
interface HealthCheck {
  ok: boolean;
  latency_ms: number;
  detail: string;
}
interface HealthResponse {
  checks: Record<string, HealthCheck>;
  overall: "ok" | "degraded" | "down";
}
interface StatsResponse {
  period_days: number;
  totals: { summaries: number; anomalies: number; alerts_sent: number; alerts_failed: number };
  daily: { date: string; summaries: number; anomalies: number; alerts: number }[];
  anomalies_by_severity: { low: number; medium: number; high: number };
  alerts_by_channel: Record<string, number>;
  log_volume: { date: string; error: number; warn: number; info: number }[];
  top_services: { service: string; error_count: number }[];
}
```

---

## Frontend

### New page: `loggator-web/app/health/page.tsx` + `HealthClient.tsx`

`page.tsx` is a thin server component that renders `<HealthClient />`.

`HealthClient.tsx` is a `"use client"` component:
- On mount: fetch `/api/v1/health`, then `setInterval(fetch, 10_000)`.
- "Refresh" button: clears and resets the interval, triggers immediate fetch.
- "Last checked X seconds ago" counter: `setInterval(updateLabel, 1_000)` using `Date.now()` diff from last fetch timestamp.
- While loading (first render): skeleton pulse on all 5 cards.

**Layout:**
- Header row: page title "System Health" | overall status badge (green/amber/red) | "Refresh" button | "Last checked Xs ago" label
- 5-card grid: `grid-cols-2 md:grid-cols-3 lg:grid-cols-5`
- Each card shows: coloured dot, service name, latency badge (hidden for scheduler/alerts), detail text

**Overall status colours:**
- `ok` → `text-emerald-400` + `bg-emerald-400/10`
- `degraded` → `text-amber-400` + `bg-amber-400/10`
- `down` → `text-red-400` + `bg-red-400/10`

---

### New page: `loggator-web/app/stats/page.tsx`

Server component. Accepts `searchParams: Promise<{ days?: string }>` (Next.js 15 pattern). Validates `days` to 7 or 30 (defaults to 7). Fetches `/api/v1/stats?days=N` server-side.

**Layout (top to bottom):**

1. **Header row** — "Statistics" title + period toggle tabs: `7d` / `30d` as `<a href>` links (no client JS)
2. **Row 1 — 4 `StatCard` components** (reuse existing component):
   - Total Summaries, Total Anomalies, Alerts Sent, Alerts Failed
3. **Row 2 — Daily activity AreaChart** (reuse `AnomalyChart` pattern):
   - 3 area series: summaries (cyan), anomalies (amber), alerts (rose)
4. **Row 3 — two columns:**
   - Left: **Log volume stacked BarChart** (ERROR=red, WARN=amber, INFO=slate) — Recharts `BarChart` with 3 stacked `Bar` components
   - Right: **Top error services** — ranked list, each row: service name + count + inline bar (width = `(count / max) * 100%`)
5. **Row 4 — two columns:**
   - Left: **Anomalies by severity** — 3 coloured pills: `low (N)` green, `medium (N)` amber, `high (N)` red
   - Right: **Alerts by channel** — pill list one per channel with count

If OpenSearch data is unavailable (empty arrays): Row 3 left panel shows a "Log data unavailable" placeholder rather than an empty chart.

---

### Navigation

**`loggator-web/components/SidebarNav.tsx`** — add two entries between Reports and Chat:

```tsx
{ href: "/stats",  label: "Statistics", icon: BarChart2 },
{ href: "/health", label: "Health",     icon: Activity  },
```

Icons from `lucide-react` (already installed).

---

## File Summary

| File | Change |
|------|--------|
| `loggator-api/loggator/api/routes/health.py` | New — 5-check health endpoint |
| `loggator-api/loggator/api/routes/stats.py` | New — aggregate stats endpoint |
| `loggator-api/loggator/main.py` | Register 2 new routers |
| `loggator-web/lib/types.ts` | Add `HealthResponse`, `HealthCheck`, `StatsResponse` |
| `loggator-web/lib/api.ts` | Add `health()`, `stats()` methods |
| `loggator-web/app/health/page.tsx` | New — thin server wrapper |
| `loggator-web/app/health/HealthClient.tsx` | New — client component with auto-refresh |
| `loggator-web/app/stats/page.tsx` | New — server component stats page |
| `loggator-web/components/SidebarNav.tsx` | Add Statistics + Health nav links |

No new pip packages. No DB migrations needed.

---

## Verification

1. **Health page** — visit `/health`; all 5 cards render; stop OpenSearch → opensearch card turns red, overall shows "Degraded" within 10s.
2. **Manual refresh** — click Refresh button; "last checked" resets to "0s ago" immediately.
3. **Stats page** — visit `/stats`; 4 stat cards show counts; charts render; switch to `?days=30` via tab → data updates.
4. **Graceful degradation** — stop OpenSearch → stats page still loads (log_volume panel shows placeholder, PostgreSQL data shows normally).
5. **API** — `GET /api/v1/health` returns JSON within 3s; `GET /api/v1/stats?days=7` returns all fields.
