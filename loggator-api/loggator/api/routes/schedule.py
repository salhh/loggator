from pathlib import Path
from typing import Optional

from apscheduler.triggers.interval import IntervalTrigger
from fastapi import APIRouter
from pydantic import BaseModel, Field

from loggator.config import settings
from loggator.db.session import AsyncSessionLocal
from loggator.db.repository import ScheduledAnalysisRepository

router = APIRouter(prefix="/schedule", tags=["schedule"])

# Path to the .env file used by the container
import os as _os
_ENV_PATH = Path(_os.environ.get("ENV_FILE_PATH", Path(__file__).resolve().parents[4] / ".env"))


class ScheduleStatusOut(BaseModel):
    enabled: bool
    interval_minutes: int
    window_minutes: int
    next_run_at: Optional[str]
    last_run_at: Optional[str]
    last_run_status: Optional[str]


class ScheduleUpdateIn(BaseModel):
    enabled: Optional[bool] = None
    interval_minutes: Optional[int] = Field(None, ge=1, le=1440)
    window_minutes: Optional[int] = Field(None, ge=1, le=1440)


@router.get("/status", response_model=ScheduleStatusOut)
async def get_schedule_status():
    from loggator.pipelines.scheduler import get_scheduler
    scheduler = get_scheduler()
    next_run_at = None
    if scheduler and scheduler.running:
        job = scheduler.get_job("scheduled_analysis")
        if job and job.next_run_time:
            next_run_at = job.next_run_time.isoformat()

    async with AsyncSessionLocal() as session:
        latest = await ScheduledAnalysisRepository(session).get_latest()

    return ScheduleStatusOut(
        enabled=settings.analysis_enabled,
        interval_minutes=settings.analysis_interval_minutes,
        window_minutes=settings.analysis_window_minutes,
        next_run_at=next_run_at,
        last_run_at=latest.created_at.isoformat() if latest else None,
        last_run_status=latest.status if latest else None,
    )


@router.put("", response_model=ScheduleStatusOut)
async def update_schedule(body: ScheduleUpdateIn):
    """Update schedule config and live-reschedule the APScheduler job."""
    from loggator.pipelines.scheduler import get_scheduler

    updates: dict[str, str] = {}

    if body.enabled is not None:
        settings.analysis_enabled = body.enabled
        updates["ANALYSIS_ENABLED"] = str(body.enabled).lower()

    if body.interval_minutes is not None:
        settings.analysis_interval_minutes = body.interval_minutes
        updates["ANALYSIS_INTERVAL_MINUTES"] = str(body.interval_minutes)

    if body.window_minutes is not None:
        settings.analysis_window_minutes = body.window_minutes
        updates["ANALYSIS_WINDOW_MINUTES"] = str(body.window_minutes)

    # Persist to .env for restarts
    if updates and _ENV_PATH.exists():
        lines = _ENV_PATH.read_text(encoding="utf-8").splitlines()
        for key, val in updates.items():
            replaced = False
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={val}"
                    replaced = True
                    break
            if not replaced:
                lines.append(f"{key}={val}")
        _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Live-reschedule the APScheduler job
    scheduler = get_scheduler()
    if scheduler and scheduler.running and body.interval_minutes is not None:
        scheduler.reschedule_job(
            "scheduled_analysis",
            trigger=IntervalTrigger(minutes=body.interval_minutes),
        )

    return await get_schedule_status()
