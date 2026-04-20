from datetime import datetime, timezone
from typing import Any, Optional

import structlog
from opensearchpy import AsyncOpenSearch

log = structlog.get_logger()

# Sort fields for search_after — timestamp first, then _id for tie-breaking
_SORT = [{"@timestamp": "asc"}, {"_id": "asc"}]


async def search_after_logs(
    client: AsyncOpenSearch,
    index: str,
    sort_cursor: Optional[list] = None,
    size: int = 500,
) -> tuple[list[dict], Optional[list]]:
    """
    Fetch a page of logs after the given sort cursor using search_after.
    Returns (hits, next_cursor). next_cursor is None if no results.
    """
    body: dict[str, Any] = {"sort": _SORT, "size": size, "query": {"match_all": {}}}
    if sort_cursor:
        body["search_after"] = sort_cursor

    try:
        response = await client.search(index=index, body=body)
    except Exception as exc:
        log.error("opensearch.search_after.error", error=str(exc))
        raise

    hits = response["hits"]["hits"]
    if not hits:
        return [], None

    next_cursor = hits[-1]["sort"]
    docs = [h["_source"] for h in hits]
    return docs, next_cursor


async def range_query_logs(
    client: AsyncOpenSearch,
    index: str,
    from_ts: datetime,
    to_ts: datetime,
    size: int = 500,
) -> list[dict]:
    """
    Fetch all logs within [from_ts, to_ts] using paginated range queries.
    Returns flat list of _source documents.
    """
    from_iso = from_ts.astimezone(timezone.utc).isoformat()
    to_iso = to_ts.astimezone(timezone.utc).isoformat()

    query = {
        "range": {
            "@timestamp": {"gte": from_iso, "lte": to_iso}
        }
    }

    all_docs: list[dict] = []
    sort_cursor: Optional[list] = None

    while True:
        body: dict[str, Any] = {"sort": _SORT, "size": size, "query": query}
        if sort_cursor:
            body["search_after"] = sort_cursor

        try:
            response = await client.search(index=index, body=body)
        except Exception as exc:
            log.error("opensearch.range_query.error", error=str(exc))
            raise

        hits = response["hits"]["hits"]
        if not hits:
            break

        all_docs.extend(h["_source"] for h in hits)
        sort_cursor = hits[-1]["sort"]

        # Stop if we got fewer results than page size
        if len(hits) < size:
            break

    log.info("opensearch.range_query.done", count=len(all_docs), from_ts=from_iso, to_ts=to_iso)
    return all_docs


async def list_indices(client: AsyncOpenSearch) -> list[str]:
    """Return all index names visible to the client."""
    response = await client.cat.indices(format="json")
    return sorted(idx["index"] for idx in response if not idx["index"].startswith("."))


async def ping(client: AsyncOpenSearch) -> bool:
    try:
        return await client.ping()
    except Exception:
        return False
