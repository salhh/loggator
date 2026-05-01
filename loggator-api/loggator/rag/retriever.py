import httpx
import structlog
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings

log = structlog.get_logger()

async def _embed_query(query: str) -> list[float]:
    url = f"{settings.ollama_base_url}/api/embeddings"
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            url,
            json={"model": settings.ollama_embed_model, "prompt": query},
        )
        resp.raise_for_status()
        return resp.json()["embedding"]


async def retrieve(
    query: str, session: AsyncSession, tenant_id: UUID, top_k: int = 10,
) -> list[str]:
    """Return the top_k most semantically similar log lines for the query."""
    embedding = await _embed_query(query)

    # pgvector cosine distance operator: <=>
    result = await session.execute(
        text(
            "SELECT text FROM log_embeddings "
            "WHERE tenant_id = CAST(:tid AS uuid) "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT :k"
        ),
        {"tid": str(tenant_id), "emb": str(embedding), "k": top_k},
    )
    rows = result.fetchall()
    log.info("retriever.retrieved", count=len(rows), query=query[:80])
    return [row[0] for row in rows]
