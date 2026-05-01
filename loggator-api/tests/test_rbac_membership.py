"""RBAC helpers: membership-based tenant admin vs platform JWT."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
from fastapi import HTTPException

from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.tenancy.authz import assert_platform_or_membership_roles, assert_tenant_admin_or_platform

TID = UUID("a0000000-0000-0000-0000-000000000099")


@pytest.mark.asyncio
async def test_tenant_admin_platform_jwt_ok(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    user = UserClaims(user_id="sub-1", platform_roles=["platform_admin"])
    await assert_tenant_admin_or_platform(session, user, TID)


@pytest.mark.asyncio
async def test_tenant_admin_membership_ok(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    user = UserClaims(user_id="sub-1", platform_roles=[])
    with patch(
        "loggator.tenancy.authz.subject_has_tenant_role",
        new_callable=AsyncMock,
        return_value=True,
    ):
        await assert_tenant_admin_or_platform(session, user, TID)


@pytest.mark.asyncio
async def test_tenant_admin_denied_without_membership(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    user = UserClaims(user_id="sub-1", platform_roles=[])
    with patch(
        "loggator.tenancy.authz.subject_has_tenant_role",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            await assert_tenant_admin_or_platform(session, user, TID)
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_auth_disabled_skips_tenant_admin_check(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    session = AsyncMock()
    await assert_tenant_admin_or_platform(session, None, TID)


@pytest.mark.asyncio
async def test_member_can_list_guard(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    user = UserClaims(user_id="sub-1", platform_roles=[])
    with patch(
        "loggator.tenancy.authz.subject_has_tenant_role",
        new_callable=AsyncMock,
        return_value=True,
    ):
        await assert_platform_or_membership_roles(
            session, user, TID, {"tenant_admin", "tenant_member"}
        )


@pytest.mark.asyncio
async def test_member_list_denied_if_no_membership(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    user = UserClaims(user_id="sub-1", platform_roles=[])
    with patch(
        "loggator.tenancy.authz.subject_has_tenant_role",
        new_callable=AsyncMock,
        return_value=False,
    ):
        with pytest.raises(HTTPException) as exc:
            await assert_platform_or_membership_roles(
                session, user, TID, {"tenant_admin", "tenant_member"}
            )
        assert exc.value.status_code == 403
