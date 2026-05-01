"""List tenants (for ``X-Tenant-Id`` switching in multi-tenant mode)."""
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Tenant
from loggator.db.session import get_session

router = APIRouter(tags=["tenants"])


class TenantOut(BaseModel):
    id: UUID
    name: str
    slug: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/tenants", response_model=list[TenantOut])
async def list_active_tenants(session: AsyncSession = Depends(get_session)):
    result = await session.execute(
        select(Tenant).where(Tenant.status == "active").order_by(Tenant.name.asc())
    )
    return list(result.scalars().all())
