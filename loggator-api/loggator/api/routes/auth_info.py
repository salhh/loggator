"""Authenticated principal introspection (OIDC / JWT claims)."""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException

from loggator.auth.dependencies import require_auth
from loggator.auth.schemas import UserClaims
from loggator.config import settings

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserClaims)
async def auth_me(user: Annotated[Optional[UserClaims], Depends(require_auth)]) -> UserClaims:
    if settings.auth_disabled:
        return UserClaims(
            user_id="dev-user",
            email="dev@local",
            platform_roles=["platform_admin"],
        )
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
