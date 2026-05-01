import fnmatch
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.opensearch.client import get_effective_index_pattern, get_opensearch_for_tenant
from loggator.tenancy.deps import get_effective_tenant_id

log = structlog.get_logger()
router = APIRouter(prefix="/ingest", tags=["ingest"])


class IngestLog(BaseModel):
    """Single log event to index into OpenSearch."""

    timestamp: Optional[str] = Field(default=None, description="ISO timestamp; stored as @timestamp")
    level: Optional[str] = None
    message: str
    service: Optional[str] = None
    host: Optional[str] = None
    fields: dict[str, Any] = Field(default_factory=dict, description="Arbitrary additional fields")


class IngestIn(BaseModel):
    index: str = Field(..., description="Destination index name (must match tenant index pattern)")
    logs: list[IngestLog]
    refresh: bool = Field(default=False, description="If true, refresh index after bulk insert (slower).")


class IngestOut(BaseModel):
    ok: bool
    indexed: int
    errors: int
    index: str


def _coerce_timestamp(raw: Optional[str]) -> str:
    if raw and isinstance(raw, str) and raw.strip():
        return raw.strip()
    return datetime.now(timezone.utc).isoformat()


@router.post("/logs", response_model=IngestOut)
async def ingest_logs(
    body: IngestIn,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    pattern = await get_effective_index_pattern(session, tenant_id)
    if not fnmatch.fnmatch(body.index, pattern):
        raise HTTPException(
            status_code=400,
            detail=f"Index {body.index!r} does not match tenant index pattern {pattern!r}",
        )

    client = await get_opensearch_for_tenant(session, tenant_id)
    bulk: list[dict] = []
    for entry in body.logs:
        doc: dict[str, Any] = {
            "@timestamp": _coerce_timestamp(entry.timestamp),
            "message": entry.message,
        }
        if entry.level:
            doc["level"] = entry.level
        if entry.service:
            doc["service"] = entry.service
        if entry.host:
            doc["host"] = entry.host
        if entry.fields:
            doc.update(entry.fields)

        bulk.append({"index": {"_index": body.index}})
        bulk.append(doc)

    try:
        resp = await client.bulk(body=bulk, refresh=body.refresh)
    except Exception as exc:
        log.error("ingest.bulk_failed", error=str(exc), index=body.index)
        raise HTTPException(status_code=502, detail=f"OpenSearch bulk failed: {exc}")

    items = resp.get("items", [])
    errors = sum(1 for it in items if (it.get("index") or {}).get("error"))
    indexed = len(body.logs) - errors
    log.info("ingest.bulk_done", index=body.index, indexed=indexed, errors=errors)
    return IngestOut(ok=errors == 0, indexed=indexed, errors=errors, index=body.index)

