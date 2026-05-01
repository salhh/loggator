from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.opensearch.client import get_opensearch_for_tenant, get_effective_index_pattern
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def list_logs(
    level: Optional[str] = Query(None, description="Comma-separated levels: INFO,WARN,ERROR"),
    service: Optional[str] = Query(None, description="Filter by service name (substring)"),
    q: Optional[str] = Query(None, description="Full-text search on message field"),
    index: Optional[str] = Query(None, description="Index pattern (default: tenant or config value)"),
    sort_field: str = Query("@timestamp", description="Field to sort by"),
    sort_dir: str = Query("desc", description="asc or desc"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    client = await get_opensearch_for_tenant(session, tenant_id)
    index_pattern = index or await get_effective_index_pattern(session, tenant_id)

    must: list = []

    if level:
        levels = [l.strip().upper() for l in level.split(",")]
        must.append({"terms": {"level.keyword": levels}})

    if service:
        must.append({"wildcard": {"service.keyword": f"*{service}*"}})

    if q:
        must.append({"match": {"message": {"query": q, "operator": "or"}}})

    query = {"bool": {"must": must}} if must else {"match_all": {}}

    body = {
        "query": query,
        "sort": [{sort_field: {"order": sort_dir}}],
        "size": limit,
        "from": offset,
    }

    try:
        resp = await client.search(index=index_pattern, body=body)
    except Exception as e:
        return {"logs": [], "total": 0, "error": str(e)}

    hits = resp["hits"]["hits"]
    total = resp["hits"]["total"]
    total_value = total["value"] if isinstance(total, dict) else total

    logs = [
        {
            "id": h["_id"],
            "index": h["_index"],
            **h["_source"],
        }
        for h in hits
    ]

    return {"logs": logs, "total": total_value}


@router.get("/indices")
async def list_indices(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    """Return all available log indices."""
    client = await get_opensearch_for_tenant(session, tenant_id)
    try:
        resp = await client.cat.indices(format="json")
        indices = sorted(
            idx["index"] for idx in resp if not idx["index"].startswith(".")
        )
        return {"indices": indices}
    except Exception as e:
        return {"indices": [], "error": str(e)}
