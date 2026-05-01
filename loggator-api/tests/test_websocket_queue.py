"""WebSocket per-connection queue: backpressure and broadcast fan-out."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


def _make_reg(maxsize: int = 200):
    """Return a fresh _WsClient with a real asyncio.Queue."""
    from loggator.api.websocket import _WsClient
    return _WsClient(tenant_filter=None)


# ---------------------------------------------------------------------------
# broadcast_tenant_event — basic fan-out
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_enqueues_event_for_matching_client():
    """An event for tenant A is put into the queue of a client subscribed to A."""
    import loggator.api.websocket as ws_mod

    tid = uuid4()
    ws = MagicMock()
    reg = ws_mod._WsClient(tenant_filter=frozenset({tid}))

    with patch.dict(ws_mod._clients, {ws: reg}, clear=True):
        await ws_mod.broadcast_tenant_event(tid, {"type": "anomaly"})

    assert reg.queue.qsize() == 1
    item = json.loads(reg.queue.get_nowait())
    assert item["type"] == "anomaly"
    assert item["tenant_id"] == str(tid)


@pytest.mark.asyncio
async def test_broadcast_skips_client_subscribed_to_different_tenant():
    """Events for tenant A are not delivered to a client subscribed only to tenant B."""
    import loggator.api.websocket as ws_mod

    tid_a = uuid4()
    tid_b = uuid4()
    ws = MagicMock()
    reg = ws_mod._WsClient(tenant_filter=frozenset({tid_b}))

    with patch.dict(ws_mod._clients, {ws: reg}, clear=True):
        await ws_mod.broadcast_tenant_event(tid_a, {"type": "anomaly"})

    assert reg.queue.qsize() == 0


@pytest.mark.asyncio
async def test_broadcast_delivers_to_all_tenants_client():
    """A client with tenant_filter=None receives events for any tenant."""
    import loggator.api.websocket as ws_mod

    tid = uuid4()
    ws = MagicMock()
    reg = ws_mod._WsClient(tenant_filter=None)

    with patch.dict(ws_mod._clients, {ws: reg}, clear=True):
        await ws_mod.broadcast_tenant_event(tid, {"type": "summary"})

    assert reg.queue.qsize() == 1


# ---------------------------------------------------------------------------
# Backpressure: drop-oldest when queue is full
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_broadcast_drops_oldest_when_queue_full():
    """When the per-connection queue is full, the oldest item is evicted."""
    import loggator.api.websocket as ws_mod

    tid = uuid4()
    ws = MagicMock()
    reg = ws_mod._WsClient(tenant_filter=None)

    # Fill the queue to capacity with numbered events
    for i in range(ws_mod._WS_QUEUE_MAX):
        await reg.queue.put(json.dumps({"seq": i}))

    assert reg.queue.full()

    with patch.dict(ws_mod._clients, {ws: reg}, clear=True):
        await ws_mod.broadcast_tenant_event(tid, {"type": "new_event", "seq": 9999})

    # Queue should still be at max size (one dropped, one added)
    assert reg.queue.qsize() == ws_mod._WS_QUEUE_MAX

    # The first item (seq=0) was the oldest and should have been evicted;
    # drain queue and verify seq=0 is gone and seq=9999 is present
    items = []
    while not reg.queue.empty():
        items.append(json.loads(reg.queue.get_nowait()))

    seqs = [item.get("seq") for item in items]
    assert 0 not in seqs           # oldest dropped
    assert 9999 in seqs            # new event present
    assert 1 in seqs               # second-oldest preserved


@pytest.mark.asyncio
async def test_broadcast_removes_dead_websocket():
    """A client that raises on queue operations is pruned from _clients."""
    import loggator.api.websocket as ws_mod

    tid = uuid4()
    ws = MagicMock()

    bad_queue = MagicMock()
    bad_queue.put_nowait = MagicMock(side_effect=Exception("dead"))
    bad_queue.full = MagicMock(return_value=False)

    reg = ws_mod._WsClient(tenant_filter=None)
    reg.queue = bad_queue  # type: ignore[assignment]

    with patch.dict(ws_mod._clients, {ws: reg}, clear=True):
        await ws_mod.broadcast_tenant_event(tid, {"type": "anomaly"})

    assert ws not in ws_mod._clients


# ---------------------------------------------------------------------------
# _sender task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_sender_drains_queue_and_sends():
    """_sender reads from the queue and forwards each frame to the WebSocket."""
    from loggator.api.websocket import _sender

    ws = AsyncMock()
    queue: asyncio.Queue = asyncio.Queue()

    await queue.put('{"type":"ping"}')
    await queue.put('{"type":"anomaly"}')

    async def _drain():
        await _sender(ws, queue)

    task = asyncio.create_task(_drain())

    # Give the sender time to drain both items then cancel it
    await asyncio.sleep(0.05)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    assert ws.send_text.call_count == 2
    calls = [c.args[0] for c in ws.send_text.call_args_list]
    assert '{"type":"ping"}' in calls
    assert '{"type":"anomaly"}' in calls
