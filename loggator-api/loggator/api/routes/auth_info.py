"""Authenticated principal introspection (OIDC / JWT claims)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.models import Tenant
from loggator.db.session import get_session

router = APIRouter(prefix="/auth", tags=["auth"])


async def _enrich_operator_labels(session: AsyncSession, user: UserClaims) -> UserClaims:
    oid = user.operator_tenant_id
    if oid is None:
        return user
    t = await session.get(Tenant, oid)
    if t is None:
        return user
    return user.model_copy(
        update={"operator_tenant_name": t.name, "operator_tenant_slug": t.slug},
    )


@router.get("/me", response_model=UserClaims)
async def auth_me(
    session: Annotated[AsyncSession, Depends(get_session)],
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
) -> UserClaims:
    if settings.auth_disabled:
        u = UserClaims(
            user_id="dev-user",
            email="dev@local",
            platform_roles=["platform_admin"],
        )
        if settings.dev_operator_tenant_id is not None:
            u = u.model_copy(
                update={
                    "platform_roles": ["platform_admin", "msp_admin"],
                    "operator_tenant_id": settings.dev_operator_tenant_id,
                }
            )
        return await _enrich_operator_labels(session, u)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _enrich_operator_labels(session, user)
