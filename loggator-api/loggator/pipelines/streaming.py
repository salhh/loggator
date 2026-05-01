import asyncio
import structlog
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from loggator.config import settings
from loggator.db.session import AsyncSessionLocal
from loggator.db.models import Anomaly, Tenant
from loggator.db.repository import CheckpointRepository, AnomalyRepository
from loggator.opensearch.client import get_opensearch_for_tenant, get_effective_index_pattern
from loggator.opensearch.queries import search_after_logs
from loggator.processing.preprocessor import preprocess
from loggator.processing.chunker import chunk_docs
from loggator.processing.mapreduce import analyze_chunks_for_anomalies
from loggator.alerts.dispatcher import dispatch
from loggator.observability import system_event_writer
from loggator.pipelines.rule_engine import evaluate_rules
from loggator.enrichment.ioc_extractor import extract_iocs
from loggator.enrichment.lookup import enrich_anomaly_iocs

log = structlog.get_logger()

_running = False
_supervisor_task: asyncio.Task | None = None
_tenant_tasks: dict[UUID, asyncio.Task] = {}


async def _process_batch(
    docs: list[dict], index_pattern: str, session, tenant_id: UUID,
) -> list[Anomaly]:
    """Preprocess → chunk → analyze → save anomalies → dispatch alerts."""
    docs = preprocess(docs)
    if not docs:
        return []

    chunks = chunk_docs(docs, max_tokens=settings.chunk_max_tokens)
    raw_results = await analyze_chunks_for_anomalies(chunks)

    saved: list[Anomaly] = []
    repo = AnomalyRepository(session, tenant_id)

    for result in raw_results:
        if not result.get("anomalies"):
            continue

        severity = result.get("severity", "low")
        summary = result.get("summary", "")
        hints = result.get("root_cause_hints", [])

        if not summary:
            continue

        anomaly = Anomaly(
            tenant_id=tenant_id,
            index_pattern=index_pattern,
            severity=severity,
            summary=summary,
            root_cause_hints=hints,
            mitre_tactics=result.get("mitre_tactics", []),
            raw_logs=[{"text": doc.get("message", "")} for doc in docs[:5]],
            model_used={"anthropic": settings.anthropic_model, "openai": settings.openai_model}.get(settings.llm_provider, settings.ollama_model),
        )
        anomaly = await repo.save(anomaly)

        # Enrich IOCs from raw logs
        try:
            iocs = extract_iocs([{"message": doc.get("text", "")} for doc in (anomaly.raw_logs or [])])
            if any(iocs.values()):
                enrichment = await enrich_anomaly_iocs(session, iocs)
                anomaly.enrichment_context = enrichment
                await session.commit()
        except Exception:
            pass

        saved.append(anomaly)

        try:
            from loggator.api.websocket import broadcast_tenant_event

            await broadcast_tenant_event(
                tenant_id,
                {
                    "type": "anomaly",
                    "anomaly_id": str(anomaly.id),
                    "severity": anomaly.severity,
                    "summary": anomaly.summary,
                    "detected_at": anomaly.detected_at.isoformat(),
                    "index_pattern": anomaly.index_pattern,
                },
            )
        except Exception:
            pass

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
                "tenant_id": str(tenant_id),
            },
        )

    return saved


async def _tenant_stream_loop(tenant_id: UUID, global_index_pattern: str | None) -> None:
    async with AsyncSessionLocal() as session:
        resolved_index = global_index_pattern or await get_effective_index_pattern(session, tenant_id)
        os_client = await get_opensearch_for_tenant(session, tenant_id)

    index_pattern = resolved_index
    log.info("streaming.tenant_started", index_pattern=index_pattern, tenant_id=str(tenant_id))

    async with AsyncSessionLocal() as session:
        cp_repo = CheckpointRepository(session, tenant_id)
        checkpoint = await cp_repo.get(index_pattern)
        sort_cursor = checkpoint.last_sort if checkpoint else None

    _backoff = 5.0  # seconds; doubles on consecutive errors, resets to 5 after success

    while _running:
        try:
            docs, new_cursor = await search_after_logs(
                os_client,
                index_pattern,
                sort_cursor=sort_cursor,
                size=settings.streaming_batch_size,
            )

            if docs:
                log.info("streaming.fetched", count=len(docs), index_pattern=index_pattern, tenant_id=str(tenant_id))
                async with AsyncSessionLocal() as session:
                    await _process_batch(docs, index_pattern, session, tenant_id)
                    # Run deterministic rule engine against the same batch
                    rule_anomalies = await evaluate_rules(
                        session, tenant_id, docs, "rule-engine", index_pattern
                    )
                    repo = AnomalyRepository(session, tenant_id)
                    for anomaly in rule_anomalies:
                        anomaly = await repo.save(anomaly)
                        try:
                            from loggator.api.websocket import broadcast_tenant_event
                            await broadcast_tenant_event(
                                tenant_id,
                                {
                                    "type": "anomaly",
                                    "anomaly_id": str(anomaly.id),
                                    "severity": anomaly.severity,
                                    "summary": anomaly.summary,
                                    "detected_at": anomaly.detected_at.isoformat(),
                                    "index_pattern": anomaly.index_pattern,
                                    "source": "rule",
                                },
                            )
                        except Exception:
                            pass
                        await dispatch(anomaly, session)

                sort_cursor = new_cursor
                if new_cursor:
                    async with AsyncSessionLocal() as session:
                        cp_repo = CheckpointRepository(session, tenant_id)
                        await cp_repo.upsert(
                            index_pattern=index_pattern,
                            last_sort=new_cursor,
                            last_seen_at=datetime.now(timezone.utc),
                        )

        except asyncio.CancelledError:
            break
        except Exception as exc:
            log.error("streaming.error", error=str(exc), tenant_id=str(tenant_id))
            await system_event_writer.write(
                service="streaming",
                event_type="error",
                severity="error",
                message=f"Streaming worker error: {exc}",
                details={"error": str(exc), "index_pattern": index_pattern, "tenant_id": str(tenant_id)},
            )
            log.warning("streaming.backoff", sleep_seconds=_backoff, tenant_id=str(tenant_id))
            await asyncio.sleep(_backoff)
            _backoff = min(_backoff * 2, 120.0)
            continue

        _backoff = 5.0
        await asyncio.sleep(settings.streaming_poll_interval_seconds)

    log.info("streaming.tenant_stopped", tenant_id=str(tenant_id))


async def run_streaming_supervisor(global_index_pattern: str | None = None) -> None:
    """Refresh active tenants periodically and run one tail loop per tenant."""
    global _running, _tenant_tasks
    _running = True
    refresh_seconds = 45
    try:
        while _running:
            async with AsyncSessionLocal() as session:
                active = set(
                    (await session.execute(select(Tenant.id).where(Tenant.status == "active"))).scalars().all()
                )

            for tid in active - set(_tenant_tasks):
                _tenant_tasks[tid] = asyncio.create_task(_tenant_stream_loop(tid, global_index_pattern))

            for tid in list(_tenant_tasks):
                if tid not in active:
                    _tenant_tasks[tid].cancel()
                    del _tenant_tasks[tid]

            for _ in range(refresh_seconds):
                if not _running:
                    break
                await asyncio.sleep(1)
    finally:
        for t in list(_tenant_tasks.values()):
            t.cancel()
        _tenant_tasks.clear()
        log.info("streaming.supervisor_stopped")


def start_streaming(index_pattern: str | None = None) -> asyncio.Task:
    global _supervisor_task
    if _supervisor_task and not _supervisor_task.done():
        return _supervisor_task
    _supervisor_task = asyncio.create_task(run_streaming_supervisor(index_pattern))
    return _supervisor_task


def stop_streaming() -> None:
    global _running, _supervisor_task
    _running = False
    if _supervisor_task and not _supervisor_task.done():
        _supervisor_task.cancel()
