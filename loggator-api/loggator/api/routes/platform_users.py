"""Platform-only user directory search (for inviting members by subject)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_platform_admin
from loggator.auth.schemas import UserClaims
from loggator.db.models import User
from loggator.db.session import get_session

router = APIRouter(prefix="/platform", tags=["platform"])


class PlatformUserOut(BaseModel):
    id: UUID
    subject: str
    email: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/users", response_model=list[PlatformUserOut])
async def search_platform_users(
    session: AsyncSession = Depends(get_session),
    _: UserClaims = Depends(require_platform_admin),
    search: str | None = Query(None, description="Filter by subject or email (contains)"),
    limit: int = Query(50, ge=1, le=200),
):
    stmt = select(User).order_by(User.created_at.desc()).limit(limit)
    if search and search.strip():
        term = f"%{search.strip()}%"
        stmt = (
            select(User)
            .where(or_(User.subject.ilike(term), User.email.ilike(term)))
            .order_by(User.created_at.desc())
            .limit(limit)
        )
    result = await session.execute(stmt)
    return list(result.scalars().all())
