from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session, AsyncSessionLocal
from loggator.llm.chain import llm_chain, LLMChain
from loggator.llm.prompts import CHAT_SYSTEM
from loggator.rag.context_fallback import recent_log_lines_from_opensearch
from loggator.rag.retriever import retrieve
from loggator.rag.embedder import index_docs
from loggator.processing.mapreduce import analyze_chunks
from loggator.processing.chunker import chunk_docs
from loggator.opensearch.client import get_opensearch_for_tenant, get_effective_index_pattern
from loggator.opensearch.queries import range_query_logs
from loggator.processing.preprocessor import preprocess
from loggator.tenancy.deps import get_effective_tenant_id

log = structlog.get_logger()
router = APIRouter(tags=["chat"])


async def _get_chain(
    model_id: Optional[str], session: AsyncSession, tenant_id: UUID,
) -> LLMChain:
    """Return the global chain or build one from a registered config."""
    if not model_id:
        return llm_chain
    from loggator.db.llm_registry import get_llm_raw, LLMNotFound
    try:
        config = await get_llm_raw(session, tenant_id, model_id)
    except LLMNotFound:
        return llm_chain
    return LLMChain(config=config)


class ChatIn(BaseModel):
    message: str
    top_k: int = 10
    model_id: Optional[str] = None


class ChatOut(BaseModel):
    answer: str
    context_logs: list[str]


@router.post("/chat", response_model=ChatOut)
async def chat(
    body: ChatIn,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    logs: list[str] = []
    try:
        logs = await retrieve(body.message, session, tenant_id, top_k=body.top_k)
    except Exception as exc:
        log.warning("chat.vector_retrieve_failed", error=str(exc))

    if not logs:
        cap = max(body.top_k * 5, 80)
        logs = await recent_log_lines_from_opensearch(
            session, tenant_id, max_lines=cap, hours_back=24.0
        )
        if logs:
            log.info("chat.used_opensearch_fallback", lines=len(logs))

    if not logs:
        log.info("chat.no_context")
        return ChatOut(
            answer=(
                "No log context is available. Seed or ingest logs into OpenSearch, "
                "then use **Index for chat** (and wait ~1 minute for embeddings), or ask again "
                f"after confirming data exists for index pattern `{settings.opensearch_index_pattern}`."
            ),
            context_logs=[],
        )

    context = "\n".join(f"- {line}" for line in logs)
    messages = [
        SystemMessage(content=CHAT_SYSTEM),
        HumanMessage(content=f"Log context:\n{context}\n\nQuestion: {body.message}"),
    ]
    chain = await _get_chain(body.model_id, session, tenant_id)
    answer = await chain.ainvoke(messages)
    return ChatOut(answer=answer, context_logs=logs)


class IndexIn(BaseModel):
    index_pattern: str = settings.opensearch_index_pattern
    hours_back: int = 1
    size: int = 500


async def _run_index(
    tenant_id: UUID, index_pattern: str, hours_back: int, size: int,
) -> None:
    from datetime import datetime, timezone, timedelta

    async with AsyncSessionLocal() as session:
        os_client = await get_opensearch_for_tenant(session, tenant_id)
        resolved_pattern = index_pattern or await get_effective_index_pattern(session, tenant_id)

    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(hours=hours_back)
    docs = await range_query_logs(os_client, resolved_pattern, from_ts, to_ts, size=size)
    docs = preprocess(docs)

    async with AsyncSessionLocal() as session:
        await index_docs(docs, resolved_pattern, session, tenant_id)


@router.post("/chat/index", status_code=202)
async def trigger_index(
    body: IndexIn,
    background_tasks: BackgroundTasks,
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    background_tasks.add_task(_run_index, tenant_id, body.index_pattern, body.hours_back, body.size)
    return {"message": "Indexing started", "index_pattern": body.index_pattern}


class AnalyzeIn(BaseModel):
    index_pattern: str = settings.opensearch_index_pattern
    hours_back: float = 1.0
    size: int = 500
    model_id: Optional[str] = None


@router.post("/chat/analyze")
async def analyze_logs(
    body: AnalyzeIn,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    from datetime import datetime, timezone, timedelta

    async with AsyncSessionLocal() as s2:
        os_client = await get_opensearch_for_tenant(s2, tenant_id)
        pattern = body.index_pattern or await get_effective_index_pattern(s2, tenant_id)

    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(hours=body.hours_back)

    docs = await range_query_logs(os_client, pattern, from_ts, to_ts, size=body.size)
    docs = preprocess(docs)

    if not docs:
        return {
            "summary": "No logs found in the specified time range.",
            "affected_services": [], "root_causes": [], "timeline": [],
            "recommendations": [], "error_count": 0, "warning_count": 0, "log_count": 0,
        }

    chunks = chunk_docs(docs)
    chain = await _get_chain(body.model_id, session, tenant_id)
    result = await analyze_chunks(chunks, chain=chain)
    result["log_count"] = len(docs)
    result["chunk_count"] = len(chunks)
    result["from_ts"] = from_ts.isoformat()
    result["to_ts"] = to_ts.isoformat()
    return result
