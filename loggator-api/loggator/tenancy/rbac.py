"""FastAPI dependencies for membership-based RBAC."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.db.session import get_session
from loggator.tenancy.authz import assert_tenant_admin_or_platform
from loggator.tenancy.deps import get_effective_tenant_id


async def require_membership_tenant_admin(
    session: Annotated[AsyncSession, Depends(get_session)],
    tenant_id: Annotated[UUID, Depends(get_effective_tenant_id)],
    user: Annotated[Optional[UserClaims], Depends(require_auth)],
) -> Optional[UserClaims]:
    await assert_tenant_admin_or_platform(session, user, tenant_id)
    return user
