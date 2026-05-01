from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Tenant


async def get_default_tenant_id(session: AsyncSession) -> UUID:
    """
    Default tenant for ingest and memberships: prefer first active **customer** tenant
    (not operator, not soft-deleted). Falls back to any active non-deleted tenant.
    """
    q_customer = (
        select(Tenant.id)
        .where(
            Tenant.status == "active",
            Tenant.deleted_at.is_(None),
            Tenant.is_operator.is_(False),
        )
        .order_by(Tenant.created_at.asc())
        .limit(1)
    )
    tid = (await session.execute(q_customer)).scalar_one_or_none()
    if tid is not None:
        return tid

    q_any = (
        select(Tenant.id)
        .where(Tenant.status == "active", Tenant.deleted_at.is_(None))
        .order_by(Tenant.created_at.asc())
        .limit(1)
    )
    tid = (await session.execute(q_any)).scalar_one_or_none()
    if tid is None:
        raise RuntimeError("No active tenant in database; run Alembic migrations.")
    return tid
