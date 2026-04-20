import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session, AsyncSessionLocal
from loggator.rag.retriever import retrieve
from loggator.rag.embedder import index_docs

router = APIRouter(tags=["chat"])

_SYSTEM = (
    "You are a log analysis assistant. Use the provided log context to answer the user's question. "
    "Be concise. If the logs don't contain relevant information, say so."
)


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
    prompt = f"Log context:\n{context}\n\nQuestion: {body.message}"

    async with httpx.AsyncClient(timeout=120) as http:
        resp = await http.post(
            f"{settings.ollama_base_url}/api/generate",
            json={"model": settings.ollama_model, "system": _SYSTEM, "prompt": prompt, "stream": False},
        )
        resp.raise_for_status()
        answer = resp.json().get("response", "")

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
