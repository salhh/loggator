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

        await asyncio.wait_for(_query(), timeout=_TIMEOUT)
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
