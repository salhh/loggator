"""User self-provisioning: get_or_create_user + ensure_default_membership."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# get_or_create_user
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creates_user_when_none_exists():
    """Creates a new User row when the subject has no existing record."""
    from loggator.tenancy.membership import get_or_create_user

    session = AsyncMock()
    session.add = MagicMock()   # add() is synchronous in SQLAlchemy
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    user, created = await get_or_create_user(session, "sub|new", "new@example.com")

    assert created is True
    session.add.assert_called_once()
    session.flush.assert_called_once()
    assert user.subject == "sub|new"
    assert user.email == "new@example.com"


@pytest.mark.asyncio
async def test_returns_existing_user_without_insert():
    """Returns the existing User row without touching the DB when found."""
    from loggator.db.models import User
    from loggator.tenancy.membership import get_or_create_user

    existing = User(subject="sub|existing", email="existing@example.com")
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result)

    user, created = await get_or_create_user(session, "sub|existing", "existing@example.com")

    assert created is False
    assert user is existing
    session.add.assert_not_called()
    session.flush.assert_not_called()


@pytest.mark.asyncio
async def test_none_email_stored_as_empty_string():
    """Stores empty string when email is None so the NOT NULL constraint holds."""
    from loggator.tenancy.membership import get_or_create_user

    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)

    user, created = await get_or_create_user(session, "sub|noemail", None)

    assert created is True
    assert user.email == ""


# ---------------------------------------------------------------------------
# ensure_default_membership
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_creates_membership_when_absent():
    """Adds a tenant_member Membership for the bootstrap tenant on first login."""
    from loggator.db.models import User
    from loggator.tenancy.membership import ensure_default_membership

    tenant_id = uuid4()
    user = User(subject="sub|new", email="new@example.com")
    user.id = uuid4()

    session = AsyncMock()
    session.add = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None  # no existing membership
    session.execute = AsyncMock(return_value=result)

    with patch(
        "loggator.tenancy.bootstrap.get_default_tenant_id",
        new_callable=AsyncMock,
        return_value=tenant_id,
    ):
        await ensure_default_membership(session, user)

    session.add.assert_called_once()
    added = session.add.call_args[0][0]
    assert added.role == "tenant_member"
    assert added.tenant_id == tenant_id
    assert added.user_id == user.id
    session.flush.assert_called_once()


@pytest.mark.asyncio
async def test_skips_membership_when_already_exists():
    """Does not create a duplicate Membership when one already exists."""
    from loggator.db.models import User
    from loggator.tenancy.membership import ensure_default_membership

    tenant_id = uuid4()
    user = User(subject="sub|existing", email="existing@example.com")
    user.id = uuid4()

    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = uuid4()  # membership id exists
    session.execute = AsyncMock(return_value=result)

    with patch(
        "loggator.tenancy.bootstrap.get_default_tenant_id",
        new_callable=AsyncMock,
        return_value=tenant_id,
    ):
        await ensure_default_membership(session, user)

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_skips_gracefully_when_no_bootstrap_tenant():
    """Does not raise if no active tenant exists in the database."""
    from loggator.db.models import User
    from loggator.tenancy.membership import ensure_default_membership

    user = User(subject="sub|new", email="new@example.com")
    user.id = uuid4()
    session = AsyncMock()

    with patch(
        "loggator.tenancy.bootstrap.get_default_tenant_id",
        side_effect=RuntimeError("No active tenant in database"),
    ):
        await ensure_default_membership(session, user)  # must not raise

    session.add.assert_not_called()
