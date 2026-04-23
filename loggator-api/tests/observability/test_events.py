"""Unit tests for SystemEventWriter de-duplication logic."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from loggator.observability.events import SystemEventWriter


@pytest.mark.asyncio
async def test_info_event_always_written():
    """info events bypass de-duplication and always write."""
    writer = SystemEventWriter()
    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()  # add() is synchronous on AsyncSession

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="scheduler",
            event_type="batch_started",
            severity="info",
            message="Batch pipeline started",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_error_event_deduplicated_when_open_event_exists():
    """error events are skipped when an identical open event exists within 5 min."""
    writer = SystemEventWriter()

    mock_existing = MagicMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_existing

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )

    mock_session.add.assert_not_called()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_error_event_written_when_no_open_event():
    """error event is written when no matching open event exists."""
    writer = SystemEventWriter()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.add = MagicMock()  # add() is synchronous on AsyncSession
    mock_session.execute = AsyncMock(return_value=mock_result)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )

    mock_session.add.assert_called_once()
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_db_failure_does_not_propagate():
    """If the DB is unavailable, write() silently falls back to structlog."""
    writer = SystemEventWriter()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(side_effect=Exception("DB connection refused"))
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with patch("loggator.observability.events.AsyncSessionLocal", return_value=mock_session):
        # Must not raise
        await writer.write(
            service="llm",
            event_type="error",
            severity="error",
            message="LLM failed",
        )
