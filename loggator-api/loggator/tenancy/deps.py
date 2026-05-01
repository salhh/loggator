from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Membership, Tenant
from loggator.db.session import get_session
from loggator.tenancy.bootstrap import get_default_tenant_id


async def get_effective_tenant_id(
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> UUID:
    """
    Resolve tenant for the request.
    - If ``X-Tenant-Id`` is set, it must refer to an active tenant.
    - Otherwise use the default (bootstrap) tenant.
    """
    # Auth disabled or anonymous: preserve single-tenant dev behavior.
    if settings.auth_disabled or user is None:
        if x_tenant_id:
            try:
                tid = UUID(x_tenant_id.strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header")
            row = await session.get(Tenant, tid)
            if row is None or row.status != "active":
                raise HTTPException(status_code=404, detail="Tenant not found or inactive")
            request.state.tenant_id = tid
            return tid
        tid = await get_default_tenant_id(session)
        request.state.tenant_id = tid
        return tid

    # Auth enabled: resolve from claims + header (multi-tenant tokens).
    chosen: UUID | None = user.tenant_id
    if chosen is None:
        if not x_tenant_id:
            raise HTTPException(status_code=400, detail="X-Tenant-Id header required for multi-tenant tokens")
        try:
            chosen = UUID(x_tenant_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header")

    tenant = await session.get(Tenant, chosen)
    if tenant is None or tenant.status != "active":
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")

    is_platform_admin = "platform_admin" in (user.platform_roles or [])
    if not is_platform_admin:
        result = await session.execute(
            select(Membership).where(
                Membership.user_id == user.user_id,
                Membership.tenant_id == chosen,
            ).limit(1)
        )
        membership = result.scalar_one_or_none()
        if membership is None:
            raise HTTPException(status_code=403, detail="Not a member of this tenant")

    request.state.tenant_id = chosen
    return chosen
