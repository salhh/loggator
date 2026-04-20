from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.repository import SummaryRepository

router = APIRouter(prefix="/summaries", tags=["summaries"])


class SummaryOut(BaseModel):
    id: UUID
    created_at: datetime
    window_start: datetime
    window_end: datetime
    index_pattern: str
    summary: str
    top_issues: list[str]
    error_count: int
    recommendation: Optional[str]
    model_used: str
    tokens_used: Optional[int]

    class Config:
        from_attributes = True


@router.get("", response_model=list[SummaryOut])
async def list_summaries(
    from_ts: Optional[datetime] = Query(None, alias="from"),
    to_ts: Optional[datetime] = Query(None, alias="to"),
    index: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = SummaryRepository(session)
    return await repo.list(from_ts=from_ts, to_ts=to_ts, index_pattern=index, limit=limit, offset=offset)


@router.get("/{id}", response_model=SummaryOut)
async def get_summary(id: UUID, session: AsyncSession = Depends(get_session)):
    repo = SummaryRepository(session)
    summary = await repo.get(id)
    if not summary:
        raise HTTPException(status_code=404, detail="Summary not found")
    return summary
