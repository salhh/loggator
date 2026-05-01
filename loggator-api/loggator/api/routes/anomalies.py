from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.models import Anomaly
from loggator.db.session import get_session
from loggator.db.repository import AnomalyRepository
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

VALID_TRIAGE_STATUSES = {"new", "acknowledged", "suppressed", "false_positive"}


class AnomalyOut(BaseModel):
    id: UUID
    detected_at: datetime
    log_timestamp: Optional[datetime]
    index_pattern: str
    severity: str
    summary: str
    root_cause_hints: list[str]
    mitre_tactics: list[str]
    raw_logs: Optional[list]
    enrichment_context: Optional[dict]
    model_used: str
    alerted: bool
    source: str
    triage_status: str
    triage_note: Optional[str]
    triaged_at: Optional[datetime]

    class Config:
        from_attributes = True


class TriageIn(BaseModel):
    status: str
    note: Optional[str] = None


@router.get("", response_model=list[AnomalyOut])
async def list_anomalies(
    severity: Optional[str] = Query(None, description="Comma-separated: low,medium,high"),
    tactic: Optional[str] = Query(None, description="Filter by MITRE tactic substring"),
    triage_status: Optional[str] = Query(None, description="Filter by triage status"),
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
    results = await repo.list(
        severity=severity_list, from_ts=from_ts, to_ts=to_ts,
        index_pattern=index, limit=limit, offset=offset
    )
    # Apply optional tactic and triage_status filters in Python (JSONB contains search)
    if tactic:
        tactic_lower = tactic.lower()
        results = [a for a in results if any(tactic_lower in t.lower() for t in (a.mitre_tactics or []))]
    if triage_status:
        results = [a for a in results if a.triage_status == triage_status]
    return results


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


@router.patch("/{id}/triage", response_model=AnomalyOut)
async def triage_anomaly(
    id: UUID,
    body: TriageIn,
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
    user: Optional[UserClaims] = Depends(require_auth),
):
    if body.status not in VALID_TRIAGE_STATUSES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid triage status. Must be one of: {', '.join(VALID_TRIAGE_STATUSES)}",
        )
    r = await session.execute(
        select(Anomaly).where(Anomaly.id == id, Anomaly.tenant_id == tenant_id).limit(1)
    )
    anomaly = r.scalar_one_or_none()
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    anomaly.triage_status = body.status
    anomaly.triage_note = body.note
    anomaly.triaged_at = datetime.now(timezone.utc)
    await session.commit()
    await session.refresh(anomaly)
    return anomaly
