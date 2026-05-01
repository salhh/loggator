"""Recent log lines from OpenSearch when vector retrieval is empty or unavailable."""
from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.opensearch.client import get_effective_index_pattern, get_opensearch_for_tenant
from loggator.opensearch.queries import range_query_logs
from loggator.processing.preprocessor import preprocess
from loggator.rag.embedder import format_doc_for_context

log = structlog.get_logger()


async def recent_log_lines_from_opensearch(
    session: AsyncSession,
    tenant_id: UUID,
    *,
    max_lines: int = 100,
    hours_back: float = 24.0,
) -> list[str]:
    """
    Pull the most recent preprocessed log lines from OpenSearch (time range).
    Used to ground /chat when ``log_embeddings`` has no hits or embedding fails.
    """
    os_client = await get_opensearch_for_tenant(session, tenant_id)
    pattern = await get_effective_index_pattern(session, tenant_id)
    now = datetime.now(timezone.utc)
    from_ts = now - timedelta(hours=hours_back)
    docs = await range_query_logs(
        os_client, pattern, from_ts, now, size=min(500, max_lines * 4)
    )
    docs = preprocess(docs)
    lines = [format_doc_for_context(d) for d in docs[:max_lines]]
    log.info("context_fallback.opensearch", count=len(lines), pattern=pattern, hours_back=hours_back)
    return lines
