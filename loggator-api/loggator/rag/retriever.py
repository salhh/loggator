import httpx
import structlog
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.models import LogEmbedding

log = structlog.get_logger()

_EMBED_URL = f"{settings.ollama_base_url}/api/embeddings"
_EMBED_MODEL = "nomic-embed-text"


async def _embed_query(query: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(_EMBED_URL, json={"model": _EMBED_MODEL, "prompt": query})
        resp.raise_for_status()
        return resp.json()["embedding"]


async def retrieve(query: str, session: AsyncSession, top_k: int = 10) -> list[str]:
    """Return the top_k most semantically similar log lines for the query."""
    embedding = await _embed_query(query)

    # pgvector cosine distance operator: <=>
    result = await session.execute(
        text(
            "SELECT text FROM log_embeddings "
            "ORDER BY embedding <=> CAST(:emb AS vector) "
            "LIMIT :k"
        ),
        {"emb": str(embedding), "k": top_k},
    )
    rows = result.fetchall()
    log.info("retriever.retrieved", count=len(rows), query=query[:80])
    return [row[0] for row in rows]
