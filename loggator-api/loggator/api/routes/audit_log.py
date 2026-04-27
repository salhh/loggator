from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import AuditLog
from loggator.db.session import get_session

router = APIRouter(tags=["observability"])


def _audit_dict(r: AuditLog) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "timestamp": r.timestamp.isoformat(),
        "request_id": r.request_id,
        "method": r.method,
        "path": r.path,
        "status_code": r.status_code,
        "duration_ms": r.duration_ms,
        "client_ip": r.client_ip,
        "query_params": r.query_params,
        "error_detail": r.error_detail,
        "actor_id": r.actor_id,
        "actor_type": r.actor_type,
    }


@router.get("/audit-log")
async def list_audit_log(
    path: str | None = Query(None, description="Prefix match on request path"),
    method: str | None = Query(None),
    status: str | None = Query(None, description="Exact (e.g. '200') or prefix (e.g. '5' for all 5xx)"),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    effective_from = from_ts or (now - timedelta(hours=24))
    effective_to = to_ts or now

    filters: list = [
        AuditLog.timestamp >= effective_from,
        AuditLog.timestamp <= effective_to,
    ]
    if path:
        filters.append(AuditLog.path.startswith(path))
    if method:
        filters.append(AuditLog.method == method.upper())
    if status:
        if len(status) == 1 and status.isdigit():
            # e.g. "5" → 500–599
            lo = int(status) * 100
            filters.append(
                and_(AuditLog.status_code >= lo, AuditLog.status_code < lo + 100)
            )
        elif status.isdigit():
            filters.append(AuditLog.status_code == int(status))
        else:
            raise HTTPException(status_code=422, detail="status must be digits only")

    q = (
        select(AuditLog)
        .where(and_(*filters))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    result = await session.execute(q)
    rows = result.scalars().all()
    return [_audit_dict(r) for r in rows]
