from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import SystemEvent
from loggator.db.session import get_session

router = APIRouter(tags=["observability"])


def _event_dict(e: SystemEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "timestamp": e.timestamp.isoformat(),
        "service": e.service,
        "event_type": e.event_type,
        "severity": e.severity,
        "message": e.message,
        "details": e.details,
        "resolved_at": e.resolved_at.isoformat() if e.resolved_at else None,
    }


@router.get("/system-events")
async def list_system_events(
    service: str | None = Query(None),
    severity: str | None = Query(None),
    event_type: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    effective_from = from_ts or (now - timedelta(hours=24))
    effective_to = to_ts or now

    filters: list = [
        SystemEvent.timestamp >= effective_from,
        SystemEvent.timestamp <= effective_to,
    ]
    if service:
        filters.append(SystemEvent.service == service)
    if severity:
        filters.append(SystemEvent.severity == severity)
    if event_type:
        filters.append(SystemEvent.event_type == event_type)

    # Paginated event list
    events_q = (
        select(SystemEvent)
        .where(and_(*filters))
        .order_by(SystemEvent.timestamp.desc())
        .limit(limit)
        .offset(offset)
    )
    events_result = await session.execute(events_q)
    events = events_result.scalars().all()

    # Summary: count by service and severity for the filtered window
    count_q = (
        select(SystemEvent.service, SystemEvent.severity, func.count())
        .where(and_(*filters))
        .group_by(SystemEvent.service, SystemEvent.severity)
    )
    count_result = await session.execute(count_q)
    by_service: dict[str, int] = {}
    by_severity: dict[str, int] = {}
    for svc, sev, cnt in count_result:
        by_service[svc] = by_service.get(svc, 0) + cnt
        by_severity[sev] = by_severity.get(sev, 0) + cnt

    # Total count matching filters (for pagination metadata)
    total_q = select(func.count()).select_from(SystemEvent).where(and_(*filters))
    total_result = await session.execute(total_q)
    total_count = total_result.scalar_one()

    # Open errors (last 15 min, unresolved) — drives status board dots
    cutoff_15 = now - timedelta(minutes=15)
    open_q = (
        select(SystemEvent)
        .where(
            and_(
                SystemEvent.severity.in_(["error", "critical"]),
                SystemEvent.resolved_at.is_(None),
                SystemEvent.timestamp >= cutoff_15,
            )
        )
        .order_by(SystemEvent.timestamp.desc())
    )
    open_result = await session.execute(open_q)
    open_errors = open_result.scalars().all()

    return {
        "summary": {
            "by_service": by_service,
            "by_severity": by_severity,
            "open_errors": [
                {
                    "service": e.service,
                    "event_type": e.event_type,
                    "message": e.message,
                    "timestamp": e.timestamp.isoformat(),
                }
                for e in open_errors
            ],
        },
        "events": [_event_dict(e) for e in events],
        "total": total_count,
    }


@router.get("/system-events/{event_id}")
async def get_system_event(
    event_id: str,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    result = await session.execute(
        select(SystemEvent).where(SystemEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return _event_dict(event)
