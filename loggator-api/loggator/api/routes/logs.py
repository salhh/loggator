from typing import Optional

from fastapi import APIRouter, Query

from loggator.opensearch.client import get_client
from loggator.config import settings

router = APIRouter(prefix="/logs", tags=["logs"])


@router.get("")
async def list_logs(
    level: Optional[str] = Query(None, description="Comma-separated levels: INFO,WARN,ERROR"),
    service: Optional[str] = Query(None, description="Filter by service name (substring)"),
    q: Optional[str] = Query(None, description="Full-text search on message field"),
    index: Optional[str] = Query(None, description="Index pattern (default: config value)"),
    sort_field: str = Query("@timestamp", description="Field to sort by"),
    sort_dir: str = Query("desc", description="asc or desc"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    client = get_client()
    index_pattern = index or settings.opensearch_index_pattern

    must: list = []

    # Level filter
    if level:
        levels = [l.strip().upper() for l in level.split(",")]
        must.append({"terms": {"level.keyword": levels}})

    # Service filter
    if service:
        must.append({"wildcard": {"service.keyword": f"*{service}*"}})

    # Full-text search
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
async def list_indices():
    """Return all available log indices."""
    client = get_client()
    try:
        resp = await client.cat.indices(format="json")
        indices = sorted(
            idx["index"] for idx in resp if not idx["index"].startswith(".")
        )
        return {"indices": indices}
    except Exception as e:
        return {"indices": [], "error": str(e)}
