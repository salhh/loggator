import hashlib
import httpx
import structlog
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.models import LogEmbedding

log = structlog.get_logger()

_EMBED_URL = f"{settings.ollama_base_url}/api/embeddings"
_EMBED_MODEL = "nomic-embed-text"


async def _embed(text_: str) -> list[float]:
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(_EMBED_URL, json={"model": _EMBED_MODEL, "prompt": text_})
        resp.raise_for_status()
        return resp.json()["embedding"]


def _render(doc: dict) -> str:
    ts = doc.get("@timestamp", "")
    level = doc.get("level", "INFO").upper()
    service = doc.get("service", "-")
    host = doc.get("host", "-")
    message = doc.get("message", "")
    occurrences = doc.get("_occurrences", 1)
    suffix = f" (x{occurrences})" if occurrences > 1 else ""
    return f"[{ts}] [{level}] [{service}] [{host}] {message}{suffix}"


def _doc_id(rendered: str) -> str:
    return hashlib.sha256(rendered.encode()).hexdigest()


async def index_docs(docs: list[dict], index_pattern: str, session: AsyncSession) -> int:
    """Embed docs and upsert into log_embeddings. Returns count inserted."""
    inserted = 0
    for doc in docs:
        rendered = _render(doc)
        try:
            embedding = await _embed(rendered)
        except Exception as exc:
            log.warning("embedder.embed_failed", error=str(exc))
            continue

        ts_raw = doc.get("@timestamp")
        log_timestamp = None
        if ts_raw:
            try:
                log_timestamp = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
            except ValueError:
                pass

        meta = {k: doc[k] for k in ("level", "service", "host") if k in doc}

        row = LogEmbedding(
            log_timestamp=log_timestamp,
            index_pattern=index_pattern,
            text=rendered,
            embedding=embedding,
            metadata_=meta,
        )
        session.add(row)
        inserted += 1

    await session.commit()
    log.info("embedder.indexed", count=inserted, index_pattern=index_pattern)
    return inserted
