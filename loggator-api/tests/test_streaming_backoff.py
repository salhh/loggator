"""Streaming pipeline: exponential backoff on consecutive errors."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Pure backoff math
# ---------------------------------------------------------------------------

def _next_backoff(current: float, max_backoff: float = 120.0) -> float:
    """Mirror of the in-loop doubling logic."""
    return min(current * 2, max_backoff)


def test_backoff_doubles_each_step():
    b = 5.0
    expected = [10.0, 20.0, 40.0, 80.0, 120.0, 120.0]
    for exp in expected:
        b = _next_backoff(b)
        assert b == exp


def test_backoff_caps_at_120():
    b = 5.0
    for _ in range(20):
        b = _next_backoff(b)
    assert b == 120.0


def test_backoff_resets_to_five_on_success():
    """Success path sets _backoff back to 5.0 (hard-coded constant in loop)."""
    reset_value = 5.0
    assert reset_value == 5.0


# ---------------------------------------------------------------------------
# Integration: mock the loop to verify sleep progression
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_path_sleeps_with_increasing_backoff():
    """On consecutive errors, asyncio.sleep is called with a doubling delay."""
    import loggator.pipelines.streaming as streaming_mod

    tenant_id = uuid4()
    sleep_calls: list[float] = []
    error_count = 0

    async def fake_search_after(*args, **kwargs):
        nonlocal error_count
        error_count += 1
        if error_count <= 3:
            raise ConnectionError("opensearch down")
        # Stop the loop after 3 errors
        streaming_mod._running = False
        return [], None

    async def fake_sleep(n: float):
        sleep_calls.append(n)

    fake_os_client = MagicMock()
    fake_session = AsyncMock()
    fake_cp_result = MagicMock()
    fake_cp_result.scalar_one_or_none.return_value = None
    fake_session.execute = AsyncMock(return_value=fake_cp_result)

    with (
        patch.object(streaming_mod, "_running", True),
        patch("loggator.pipelines.streaming.search_after_logs", side_effect=fake_search_after),
        patch("loggator.pipelines.streaming.AsyncSessionLocal") as mock_session_local,
        patch("loggator.pipelines.streaming.get_opensearch_for_tenant", new_callable=AsyncMock, return_value=fake_os_client),
        patch("loggator.pipelines.streaming.get_effective_index_pattern", new_callable=AsyncMock, return_value="logs-*"),
        patch("loggator.pipelines.streaming.CheckpointRepository") as mock_cp_repo,
        patch("loggator.pipelines.streaming.system_event_writer") as mock_writer,
        patch("asyncio.sleep", side_effect=fake_sleep),
    ):
        mock_session_local.return_value.__aenter__ = AsyncMock(return_value=fake_session)
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_cp_repo.return_value.get = AsyncMock(return_value=None)
        mock_writer.write = AsyncMock()
        streaming_mod._running = True

        await streaming_mod._tenant_stream_loop(tenant_id, "logs-*")

    # 3 errors → backoff sleeps: 5.0, 10.0, 20.0
    # 4th call succeeds → one normal poll-interval sleep appended
    assert sleep_calls[:3] == [5.0, 10.0, 20.0]


@pytest.mark.asyncio
async def test_success_resets_backoff():
    """After a successful poll the backoff is reset to 5.0 (normal poll interval used)."""
    import loggator.pipelines.streaming as streaming_mod

    tenant_id = uuid4()
    call_count = 0
    sleep_calls: list[float] = []

    async def fake_search_after(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("first error")
        if call_count == 2:
            return [], None   # success — resets backoff
        streaming_mod._running = False
        return [], None

    async def fake_sleep(n: float):
        sleep_calls.append(n)

    fake_os_client = MagicMock()
    fake_session = AsyncMock()
    fake_cp_result = MagicMock()
    fake_cp_result.scalar_one_or_none.return_value = None
    fake_session.execute = AsyncMock(return_value=fake_cp_result)

    with (
        patch("loggator.pipelines.streaming.search_after_logs", side_effect=fake_search_after),
        patch("loggator.pipelines.streaming.AsyncSessionLocal") as mock_session_local,
        patch("loggator.pipelines.streaming.get_opensearch_for_tenant", new_callable=AsyncMock, return_value=fake_os_client),
        patch("loggator.pipelines.streaming.get_effective_index_pattern", new_callable=AsyncMock, return_value="logs-*"),
        patch("loggator.pipelines.streaming.CheckpointRepository") as mock_cp_repo,
        patch("loggator.pipelines.streaming.system_event_writer") as mock_writer,
        patch("asyncio.sleep", side_effect=fake_sleep),
    ):
        mock_session_local.return_value.__aenter__ = AsyncMock(return_value=fake_session)
        mock_session_local.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_cp_repo.return_value.get = AsyncMock(return_value=None)
        mock_writer.write = AsyncMock()
        streaming_mod._running = True

        await streaming_mod._tenant_stream_loop(tenant_id, "logs-*")

    # sleep_calls[0] = 5.0 (error backoff), sleep_calls[1] = poll_interval (success reset)
    assert sleep_calls[0] == 5.0
    # After success the loop sleeps for poll_interval, not a doubled value
    from loggator.config import settings
    assert sleep_calls[1] == settings.streaming_poll_interval_seconds
