from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Tenant


async def get_default_tenant_id(session: AsyncSession) -> UUID:
    """First active tenant by creation time (bootstrap migration inserts one)."""
    q = (
        select(Tenant.id)
        .where(Tenant.status == "active")
        .order_by(Tenant.created_at.asc())
        .limit(1)
    )
    tid = (await session.execute(q)).scalar_one_or_none()
    if tid is None:
        raise RuntimeError("No active tenant in database; run Alembic migrations.")
    return tid
