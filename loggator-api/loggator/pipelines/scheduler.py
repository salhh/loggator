import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from loggator.config import settings

log = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None


async def _run_batch_job() -> None:
    from loggator.pipelines.batch import run_batch
    try:
        summary = await run_batch()
        if summary:
            log.info("scheduler.batch.complete", summary_id=str(summary.id),
                     error_count=summary.error_count)
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


async def _run_analysis_job() -> None:
    from loggator.pipelines.batch import run_scheduled_analysis
    if not settings.analysis_enabled:
        log.info("scheduler.analysis.disabled")
        return
    try:
        record = await run_scheduled_analysis()
        if record:
            log.info("scheduler.analysis.complete", id=str(record.id),
                     error_count=record.error_count, status=record.status)
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


def get_scheduler() -> AsyncIOScheduler | None:
    """Return the running scheduler instance (used by API routes for live rescheduling)."""
    return _scheduler


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    _scheduler = AsyncIOScheduler()

    _scheduler.add_job(
        _run_batch_job,
        trigger=IntervalTrigger(minutes=settings.batch_interval_minutes),
        id="batch_summarizer",
        name="Batch log summarizer",
        replace_existing=True,
        misfire_grace_time=60,
    )

    _scheduler.add_job(
        _run_analysis_job,
        trigger=IntervalTrigger(minutes=settings.analysis_interval_minutes),
        id="scheduled_analysis",
        name="Scheduled RCA analysis",
        replace_existing=True,
        misfire_grace_time=120,
    )

    _scheduler.start()
    log.info("scheduler.started",
             batch_interval=settings.batch_interval_minutes,
             analysis_interval=settings.analysis_interval_minutes)

    from loggator.pipelines.streaming import start_streaming
    start_streaming()
    log.info("streaming.worker.started")

    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    from loggator.pipelines.streaming import stop_streaming
    stop_streaming()
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        log.info("scheduler.stopped")
