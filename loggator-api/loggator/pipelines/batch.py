from datetime import datetime, timedelta, timezone

import structlog

from loggator.config import settings
from loggator.db.models import Summary
from loggator.db.session import AsyncSessionLocal
from loggator.db.repository import SummaryRepository
from loggator.opensearch.client import get_client
from loggator.opensearch.queries import range_query_logs
from loggator.processing.preprocessor import preprocess
from loggator.processing.chunker import chunk_docs
from loggator.processing.mapreduce import summarize_chunks

log = structlog.get_logger()


async def run_batch(
    window_minutes: int | None = None,
    index_pattern: str | None = None,
) -> Summary | None:
    """
    Fetch logs from the last N minutes, run map-reduce summarization via Ollama,
    and persist the result to PostgreSQL. Returns the saved Summary or None on error.
    """
    window = window_minutes or settings.batch_window_minutes
    index = index_pattern or settings.opensearch_index_pattern

    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(minutes=window)

    log.info("batch.start", index=index, from_ts=from_ts.isoformat(), to_ts=now.isoformat(), window_minutes=window)

    # ── 1. Fetch logs from OpenSearch ─────────────────────────────────────────
    try:
        os_client = get_client()
        raw_docs = await range_query_logs(os_client, index, from_ts, now)
    except Exception as exc:
        log.error("batch.opensearch.failed", error=str(exc))
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
        log.error("batch.ollama.failed", error=str(exc))
        return None

    log.info("batch.ollama.done", error_count=result.get("error_count", 0))

    # ── 5. Persist to PostgreSQL ───────────────────────────────────────────────
    summary = Summary(
        window_start=from_ts,
        window_end=now,
        index_pattern=index,
        summary=result.get("summary", ""),
        top_issues=result.get("top_issues", []),
        error_count=int(result.get("error_count", 0)),
        recommendation=result.get("recommendation"),
        model_used=settings.llm_provider,
        tokens_used=None,
    )

    async with AsyncSessionLocal() as session:
        repo = SummaryRepository(session)
        saved = await repo.save(summary)

    log.info("batch.saved", summary_id=str(saved.id), error_count=saved.error_count)
    return saved
