from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.repository import AnomalyRepository
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(prefix="/anomalies", tags=["anomalies"])


class AnomalyOut(BaseModel):
    id: UUID
    detected_at: datetime
    log_timestamp: Optional[datetime]
    index_pattern: str
    severity: str
    summary: str
    root_cause_hints: list[str]
    raw_logs: Optional[list]
    model_used: str
    alerted: bool

    class Config:
        from_attributes = True


@router.get("", response_model=list[AnomalyOut])
async def list_anomalies(
    severity: Optional[str] = Query(None, description="Comma-separated: low,medium,high"),
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    index: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    repo = AnomalyRepository(session, tenant_id)
    severity_list = [s.strip() for s in severity.split(",")] if severity else None
    return await repo.list(
        severity=severity_list, from_ts=from_ts, to_ts=to_ts,
        index_pattern=index, limit=limit, offset=offset
    )


@router.get("/{id}", response_model=AnomalyOut)
async def get_anomaly(
    id: UUID,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    repo = AnomalyRepository(session, tenant_id)
    anomaly = await repo.get(id)
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    return anomaly
