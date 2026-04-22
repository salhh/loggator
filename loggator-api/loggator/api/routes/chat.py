from fastapi import APIRouter, BackgroundTasks, Depends
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session, AsyncSessionLocal
from loggator.llm.chain import llm_chain
from loggator.llm.prompts import CHAT_SYSTEM
from loggator.rag.retriever import retrieve
from loggator.rag.embedder import index_docs
from loggator.processing.mapreduce import analyze_chunks
from loggator.processing.chunker import chunk_docs

router = APIRouter(tags=["chat"])


class ChatIn(BaseModel):
    message: str
    top_k: int = 10


class ChatOut(BaseModel):
    answer: str
    context_logs: list[str]


@router.post("/chat", response_model=ChatOut)
async def chat(body: ChatIn, session: AsyncSession = Depends(get_session)):
    logs = await retrieve(body.message, session, top_k=body.top_k)

    context = "\n".join(f"- {line}" for line in logs)

    messages = [
        SystemMessage(content=CHAT_SYSTEM),
        HumanMessage(content=f"Log context:\n{context}\n\nQuestion: {body.message}"),
    ]
    answer = await llm_chain.ainvoke(messages)

    return ChatOut(answer=answer, context_logs=logs)


class IndexIn(BaseModel):
    index_pattern: str = settings.opensearch_index_pattern
    hours_back: int = 1
    size: int = 500


async def _run_index(index_pattern: str, hours_back: int, size: int) -> None:
    from datetime import datetime, timezone, timedelta
    from loggator.opensearch.client import get_client
    from loggator.opensearch.queries import range_query_logs
    from loggator.processing.preprocessor import preprocess

    client = get_client()
    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(hours=hours_back)
    docs = await range_query_logs(client, index_pattern, from_ts, to_ts, size=size)
    docs = preprocess(docs)

    async with AsyncSessionLocal() as session:
        await index_docs(docs, index_pattern, session)


@router.post("/chat/index", status_code=202)
async def trigger_index(body: IndexIn, background_tasks: BackgroundTasks):
    background_tasks.add_task(_run_index, body.index_pattern, body.hours_back, body.size)
    return {"message": "Indexing started", "index_pattern": body.index_pattern}


class AnalyzeIn(BaseModel):
    index_pattern: str = settings.opensearch_index_pattern
    hours_back: float = 1.0
    size: int = 500


@router.post("/chat/analyze")
async def analyze_logs(body: AnalyzeIn):
    """
    Fetch logs for the given time window, run deep map-reduce root cause
    analysis via Ollama, and return a structured RCA report.
    """
    from datetime import datetime, timezone, timedelta
    from loggator.opensearch.client import get_client
    from loggator.opensearch.queries import range_query_logs
    from loggator.processing.preprocessor import preprocess

    client = get_client()
    to_ts = datetime.now(timezone.utc)
    from_ts = to_ts - timedelta(hours=body.hours_back)

    docs = await range_query_logs(client, body.index_pattern, from_ts, to_ts, size=body.size)
    docs = preprocess(docs)

    if not docs:
        return {
            "summary": "No logs found in the specified time range.",
            "affected_services": [],
            "root_causes": [],
            "timeline": [],
            "recommendations": [],
            "error_count": 0,
            "warning_count": 0,
            "log_count": 0,
            "chunk_count": 0,
            "from_ts": from_ts.isoformat(),
            "to_ts": to_ts.isoformat(),
        }

    chunks = chunk_docs(docs)
    result = await analyze_chunks(chunks)
    result["log_count"] = len(docs)
    result["chunk_count"] = len(chunks)
    result["from_ts"] = from_ts.isoformat()
    result["to_ts"] = to_ts.isoformat()
    return result
