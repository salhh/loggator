from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.repository import ScheduledAnalysisRepository

router = APIRouter(prefix="/analysis-reports", tags=["analysis-reports"])


class ScheduledAnalysisOut(BaseModel):
    id: UUID
    created_at: datetime
    window_start: datetime
    window_end: datetime
    index_pattern: str
    summary: str
    affected_services: list[str]
    root_causes: list[Any]
    timeline: list[Any]
    recommendations: list[Any]
    error_count: int
    warning_count: int
    log_count: int
    chunk_count: int
    model_used: str
    status: str

    class Config:
        from_attributes = True


@router.get("", response_model=list[ScheduledAnalysisOut])
async def list_reports(
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    index: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    return await ScheduledAnalysisRepository(session).list(
        from_ts=from_ts, to_ts=to_ts, index_pattern=index,
        limit=limit, offset=offset,
    )


@router.get("/{id}", response_model=ScheduledAnalysisOut)
async def get_report(id: UUID, session: AsyncSession = Depends(get_session)):
    record = await ScheduledAnalysisRepository(session).get(id)
    if not record:
        raise HTTPException(status_code=404, detail="Report not found")
    return record
