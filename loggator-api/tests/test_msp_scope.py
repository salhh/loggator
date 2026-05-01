"""MSP scoping helpers."""

from unittest.mock import AsyncMock
from uuid import UUID

import pytest

from loggator.auth.schemas import UserClaims
from loggator.config import settings
from loggator.tenancy.msp_scope import enrich_user_msp_from_db, tenant_ids_visible_to_principal


@pytest.mark.asyncio
async def test_enrich_no_db_when_operator_in_claim(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    session = AsyncMock()
    u = UserClaims(user_id="sub-1", operator_tenant_id=UUID("a0000000-0000-0000-0000-000000000001"))
    out = await enrich_user_msp_from_db(session, u)
    assert out.operator_tenant_id == u.operator_tenant_id
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_visible_principal_msp_filters(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    op = UUID("b0000000-0000-0000-0000-000000000001")
    child = UUID("c0000000-0000-0000-0000-000000000002")

    async def fake_visible_msp(_session, oid):
        assert oid == op
        return [op, child]

    monkeypatch.setattr(
        "loggator.tenancy.msp_scope.tenant_ids_visible_to_msp",
        fake_visible_msp,
    )
    user = UserClaims(
        user_id="sub-msp",
        platform_roles=["msp_admin"],
        operator_tenant_id=op,
    )
    session = AsyncMock()
    v = await tenant_ids_visible_to_principal(session, user)
    assert v == [op, child]


@pytest.mark.asyncio
async def test_visible_principal_superadmin_none(monkeypatch):
    monkeypatch.setattr(settings, "auth_disabled", False)
    user = UserClaims(user_id="sub-sa", platform_roles=["platform_admin"])
    session = AsyncMock()
    v = await tenant_ids_visible_to_principal(session, user)
    assert v is None
