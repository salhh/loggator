"""Tenant resolution for POST /ingest/logs (JWT or lgk_* API key)."""

from __future__ import annotations

from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.auth.api_keys import verify_ingest_api_key
from loggator.auth.client import IAMClient
from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.db.session import get_session
from loggator.tenancy.deps import resolve_tenant_for_principal

_bearer = HTTPBearer(auto_error=False)
_iam = IAMClient()


async def resolve_ingest_tenant_id(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
    x_api_key: Annotated[Optional[str], Header(alias="X-API-Key")] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
) -> UUID:
    raw_key = (x_api_key or "").strip() or None
    if not raw_key and credentials and credentials.credentials.startswith("lgk_"):
        raw_key = credentials.credentials.strip()
    if raw_key and raw_key.startswith("lgk_"):
        tid = await verify_ingest_api_key(session, raw_key)
        if tid is None:
            raise HTTPException(status_code=401, detail="Invalid or revoked ingest API key")
        request.state.tenant_id = tid
        request.state.auth_via = "api_key"
        return tid

    user: Optional[UserClaims] = None
    if settings.auth_disabled:
        user = None
    else:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        user = await _iam.verify_token(credentials.credentials)
        if user is None:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        request.state.user_claims = user

    tid = await resolve_tenant_for_principal(session, request, user, x_tenant_id)
    return tid
