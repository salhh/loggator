from datetime import datetime, timedelta, timezone

import structlog

from loggator.config import settings
from loggator.db.models import Summary, ScheduledAnalysis
from loggator.db.session import AsyncSessionLocal
from loggator.db.repository import SummaryRepository, ScheduledAnalysisRepository
from loggator.opensearch.client import get_client
from loggator.opensearch.queries import range_query_logs
from loggator.processing.preprocessor import preprocess
from loggator.processing.chunker import chunk_docs
from loggator.processing.mapreduce import summarize_chunks, analyze_chunks
from loggator.observability import system_event_writer

log = structlog.get_logger()

_MODEL_NAME = {
    "anthropic": lambda: settings.anthropic_model,
    "openai": lambda: settings.openai_model,
    "ollama": lambda: settings.ollama_model,
}


def _active_model() -> str:
    return _MODEL_NAME.get(settings.llm_provider, lambda: settings.ollama_model)()


async def run_batch(
    window_minutes: int | None = None,
    index_pattern: str | None = None,
) -> Summary | None:
    """
    Fetch logs from the last N minutes, run map-reduce summarization via LLM chain,
    and persist the result to PostgreSQL. Returns the saved Summary or None on error.
    """
    window = window_minutes or settings.batch_window_minutes
    index = index_pattern or settings.opensearch_index_pattern

    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(minutes=window)

    log.info("batch.start", index=index, from_ts=from_ts.isoformat(), to_ts=now.isoformat(), window_minutes=window)
    await system_event_writer.write(
        service="scheduler",
        event_type="batch_started",
        severity="info",
        message=f"Batch pipeline started for index {index} (window {window}m)",
        details={"index": index, "window_minutes": window, "from_ts": from_ts.isoformat()},
    )

    # ── 1. Fetch logs from OpenSearch ─────────────────────────────────────────
    try:
        os_client = get_client()
        raw_docs = await range_query_logs(os_client, index, from_ts, now)
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

    if not raw_docs:
        log.info("batch.no_logs", window_minutes=window)
        return None

    log.info("batch.fetched", count=len(raw_docs))

    # ── 2. Preprocess ─────────────────────────────────────────────────────────
    clean_docs = preprocess(raw_docs)
    if not clean_docs:
        log.info("batch.all_filtered")
        return None

    # ── 3. Chunk ──────────────────────────────────────────────────────────────
    chunks = chunk_docs(clean_docs)
    log.info("batch.chunked", chunks=len(chunks))

    # ── 4. Map-reduce summarize via LLM chain ─────────────────────────────────
    try:
        result = await summarize_chunks(chunks)
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

    # ── 5. Persist to PostgreSQL ───────────────────────────────────────────────
    summary = Summary(
        window_start=from_ts,
        window_end=now,
        index_pattern=index,
        summary=result.get("summary", ""),
        top_issues=result.get("top_issues", []),
        error_count=int(result.get("error_count", 0)),
        recommendation=result.get("recommendation"),
        model_used=_active_model(),
        tokens_used=None,
    )

    async with AsyncSessionLocal() as session:
        repo = SummaryRepository(session)
        saved = await repo.save(summary)

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


async def run_scheduled_analysis(
    window_minutes: int | None = None,
    index_pattern: str | None = None,
) -> ScheduledAnalysis | None:
    """
    Run both a batch summary AND a deep RCA for the configured time window.
    Saves the RCA result to scheduled_analyses. Skips if window already analysed.
    """
    window = window_minutes or settings.analysis_window_minutes
    index = index_pattern or settings.opensearch_index_pattern
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(minutes=window)

    log.info("scheduled_analysis.start", index=index, window_minutes=window,
             from_ts=from_ts.isoformat(), to_ts=now.isoformat())

    # 0. Dedup check
    async with AsyncSessionLocal() as session:
        existing = await ScheduledAnalysisRepository(session).find_by_window(from_ts, now)
        if existing:
            log.info("scheduled_analysis.skipped", reason="duplicate_window",
                     existing_id=str(existing.id))
            return None

    # 1. Fetch logs
    try:
        os_client = get_client()
        raw_docs = await range_query_logs(os_client, index, from_ts, now)
    except Exception as exc:
        log.error("scheduled_analysis.opensearch.failed", error=str(exc))
        return None

    if not raw_docs:
        log.info("scheduled_analysis.no_logs")
        return None

    # 2. Preprocess + chunk
    clean_docs = preprocess(raw_docs)
    if not clean_docs:
        log.info("scheduled_analysis.all_filtered")
        return None

    chunks = chunk_docs(clean_docs)
    log.info("scheduled_analysis.chunked", chunks=len(chunks))
    status = "success"

    # 3. Batch summary (non-fatal)
    try:
        summary_result = await summarize_chunks(chunks)
        async with AsyncSessionLocal() as session:
            await SummaryRepository(session).save(Summary(
                window_start=from_ts, window_end=now, index_pattern=index,
                summary=summary_result.get("summary", ""),
                top_issues=summary_result.get("top_issues", []),
                error_count=int(summary_result.get("error_count", 0)),
                recommendation=summary_result.get("recommendation"),
                model_used=_active_model(), tokens_used=None,
            ))
        log.info("scheduled_analysis.summary.saved")
    except Exception as exc:
        log.error("scheduled_analysis.summary.failed", error=str(exc))

    # 4. Deep RCA
    try:
        rca = await analyze_chunks(chunks)
    except Exception as exc:
        log.error("scheduled_analysis.rca.failed", error=str(exc))
        status = "failed"
        rca = {
            "summary": f"Analysis failed: {exc}",
            "affected_services": [], "root_causes": [],
            "timeline": [], "recommendations": [],
            "error_count": 0, "warning_count": 0,
        }

    # 5. Persist RCA
    record = ScheduledAnalysis(
        window_start=from_ts, window_end=now, index_pattern=index,
        summary=rca.get("summary", ""),
        affected_services=rca.get("affected_services", []),
        root_causes=rca.get("root_causes", []),
        timeline=rca.get("timeline", []),
        recommendations=rca.get("recommendations", []),
        error_count=int(rca.get("error_count", 0)),
        warning_count=int(rca.get("warning_count", 0)),
        log_count=len(clean_docs), chunk_count=len(chunks),
        model_used=_active_model(), status=status,
    )
    async with AsyncSessionLocal() as session:
        saved = await ScheduledAnalysisRepository(session).save(record)

    log.info("scheduled_analysis.saved", id=str(saved.id), status=status)
    return saved
