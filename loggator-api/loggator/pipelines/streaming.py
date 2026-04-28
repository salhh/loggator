import asyncio
import structlog
from datetime import datetime, timezone

from loggator.config import settings
from loggator.db.session import AsyncSessionLocal
from loggator.db.models import Anomaly
from loggator.db.repository import CheckpointRepository, AnomalyRepository
from loggator.opensearch.client import get_client
from loggator.opensearch.queries import search_after_logs
from loggator.processing.preprocessor import preprocess
from loggator.processing.chunker import chunk_docs
from loggator.processing.mapreduce import analyze_chunks_for_anomalies
from loggator.alerts.dispatcher import dispatch
from loggator.observability import system_event_writer

log = structlog.get_logger()

_running = False
_task: asyncio.Task | None = None


async def _process_batch(docs: list[dict], index_pattern: str, session) -> list[Anomaly]:
    """Preprocess → chunk → analyze → save anomalies → dispatch alerts."""
    docs = preprocess(docs)
    if not docs:
        return []

    chunks = chunk_docs(docs, max_tokens=settings.chunk_max_tokens)
    raw_results = await analyze_chunks_for_anomalies(chunks)

    saved: list[Anomaly] = []
    repo = AnomalyRepository(session)

    for result in raw_results:
        if not result.get("anomalies"):
            continue

        severity = result.get("severity", "low")
        summary = result.get("summary", "")
        hints = result.get("root_cause_hints", [])

        if not summary:
            continue

        anomaly = Anomaly(
            index_pattern=index_pattern,
            severity=severity,
            summary=summary,
            root_cause_hints=hints,
            mitre_tactics=result.get("mitre_tactics", []),
            raw_logs=[{"text": doc.get("message", "")} for doc in docs[:5]],
            model_used={"anthropic": settings.anthropic_model, "openai": settings.openai_model}.get(settings.llm_provider, settings.ollama_model),
        )
        anomaly = await repo.save(anomaly)
        saved.append(anomaly)

        # Broadcast to WebSocket clients
        try:
            from loggator.api.websocket import broadcast
            await broadcast({
                "type": "anomaly",
                "anomaly_id": str(anomaly.id),
                "severity": anomaly.severity,
                "summary": anomaly.summary,
                "detected_at": anomaly.detected_at.isoformat(),
                "index_pattern": anomaly.index_pattern,
            })
        except Exception:
            pass

        # Dispatch alerts (Slack / email / webhook)
        await dispatch(anomaly, session)
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

    return saved


async def run_streaming_worker(index_pattern: str | None = None) -> None:
    """Continuously tail OpenSearch using search_after, detect anomalies in real time."""
    global _running
    _running = True
    index_pattern = index_pattern or settings.opensearch_index_pattern
    log.info("streaming.started", index_pattern=index_pattern)

    os_client = get_client()

    # Resume from last checkpoint
    async with AsyncSessionLocal() as session:
        cp_repo = CheckpointRepository(session)
        checkpoint = await cp_repo.get(index_pattern)
        sort_cursor = checkpoint.last_sort if checkpoint else None

    while _running:
        try:
            docs, new_cursor = await search_after_logs(
                os_client,
                index_pattern,
                sort_cursor=sort_cursor,
                size=settings.streaming_batch_size,
            )

            if docs:
                log.info("streaming.fetched", count=len(docs), index_pattern=index_pattern)
                async with AsyncSessionLocal() as session:
                    await _process_batch(docs, index_pattern, session)

                sort_cursor = new_cursor
                if new_cursor:
                    async with AsyncSessionLocal() as session:
                        cp_repo = CheckpointRepository(session)
                        await cp_repo.upsert(
                            index_pattern=index_pattern,
                            last_sort=new_cursor,
                            last_seen_at=datetime.now(timezone.utc),
                        )

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

        await asyncio.sleep(settings.streaming_poll_interval_seconds)

    log.info("streaming.stopped")


def start_streaming(index_pattern: str | None = None) -> asyncio.Task:
    global _task
    if _task and not _task.done():
        return _task
    _task = asyncio.create_task(run_streaming_worker(index_pattern))
    return _task


def stop_streaming() -> None:
    global _running, _task
    _running = False
    if _task and not _task.done():
        _task.cancel()
