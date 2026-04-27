import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from loggator.config import settings
from loggator.observability import system_event_writer

log = structlog.get_logger()

_scheduler: AsyncIOScheduler | None = None
_batch_last_failed = False
_analysis_last_failed = False


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
