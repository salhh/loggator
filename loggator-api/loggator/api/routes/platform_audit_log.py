"""Platform / MSP cross-tenant audit log viewer."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.api.routes.audit_log import _audit_dict
from loggator.auth.dependencies import require_platform_or_msp
from loggator.auth.schemas import UserClaims
from loggator.db.models import AuditLog
from loggator.db.session import get_session
from loggator.tenancy.msp_scope import tenant_ids_visible_to_principal

router = APIRouter(prefix="/platform", tags=["platform"])


@router.get("/audit-log")
async def platform_list_audit_log(
    tenant_id: UUID | None = Query(None, description="Filter by specific tenant"),
    path: str | None = Query(None, description="Prefix match on request path"),
    method: str | None = Query(None),
    status: str | None = Query(None, description="Exact (e.g. '200') or prefix (e.g. '5' for all 5xx)"),
    actor_id: str | None = Query(None),
    from_ts: datetime | None = Query(None),
    to_ts: datetime | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    user: UserClaims = Depends(require_platform_or_msp),
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    effective_from = from_ts or (now - timedelta(hours=24))
    effective_to = to_ts or now

    filters: list = [
        AuditLog.timestamp >= effective_from,
        AuditLog.timestamp <= effective_to,
    ]
    visible = await tenant_ids_visible_to_principal(session, user)
    if visible is not None:
        if tenant_id is not None and tenant_id not in visible:
            raise HTTPException(status_code=403, detail="Tenant not in scope")
        if tenant_id is None:
            filters.append(AuditLog.tenant_id.in_(visible))
    if tenant_id is not None:
        filters.append(AuditLog.tenant_id == tenant_id)
    if path:
        filters.append(AuditLog.path.startswith(path))
    if method:
        filters.append(AuditLog.method == method.upper())
    if actor_id:
        filters.append(AuditLog.actor_id == actor_id)
    if status:
        if len(status) == 1 and status.isdigit():
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
