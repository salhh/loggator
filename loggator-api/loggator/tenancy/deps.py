from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Tenant
from loggator.db.session import get_session
from loggator.tenancy.bootstrap import get_default_tenant_id
from loggator.tenancy.membership import user_can_access_tenant


async def resolve_effective_tenant_uuid(
    session: AsyncSession,
    user: Optional[UserClaims],
    x_tenant_id: Optional[str],
) -> UUID:
    """
    Resolve active tenant UUID (HTTP header, JWT claims, or default).

    Same rules as ``resolve_tenant_for_principal`` but without touching ``request.state``.
    Used by WebSocket auth and tests.
    """
    if settings.auth_disabled or user is None:
        if x_tenant_id:
            try:
                tid = UUID(x_tenant_id.strip())
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header")
            row = await session.get(Tenant, tid)
            if row is None or row.status != "active" or row.deleted_at is not None:
                raise HTTPException(status_code=404, detail="Tenant not found or inactive")
            return tid
        return await get_default_tenant_id(session)

    chosen: UUID | None = user.tenant_id
    if chosen is None and len(user.tenant_ids) == 1:
        chosen = user.tenant_ids[0]
    if chosen is None:
        if not x_tenant_id:
            raise HTTPException(
                status_code=400,
                detail="X-Tenant-Id header required when the token has no tenant_id and multiple tenants are available",
            )
        try:
            chosen = UUID(x_tenant_id.strip())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid X-Tenant-Id header")

    tenant = await session.get(Tenant, chosen)
    if tenant is None or tenant.status != "active" or tenant.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Tenant not found or inactive")

    if not await user_can_access_tenant(session, user, chosen):
        raise HTTPException(status_code=403, detail="Not a member of this tenant")

    return chosen


async def resolve_tenant_for_principal(
    session: AsyncSession,
    request: Request,
    user: Optional[UserClaims],
    x_tenant_id: Optional[str],
) -> UUID:
    """
    Resolve active tenant from auth claims and optional ``X-Tenant-Id``.

    - Auth off: optional header picks tenant; else default bootstrap tenant.
    - Auth on: ``tenant_id`` claim, or sole ``tenant_ids`` entry, or ``X-Tenant-Id`` (required if multiple).
    - Platform admins may use ``X-Tenant-Id`` for any active tenant.
    """
    tid = await resolve_effective_tenant_uuid(session, user, x_tenant_id)
    request.state.tenant_id = tid
    return tid


async def get_effective_tenant_id(
    session: Annotated[AsyncSession, Depends(get_session)],
    request: Request,
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> UUID:
    """FastAPI dependency: tenant for the current request (JWT + optional ``X-Tenant-Id``)."""
    return await resolve_tenant_for_principal(session, request, user, x_tenant_id)
