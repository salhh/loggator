import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict
from uuid import UUID

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from loggator.auth.client import IAMClient
from loggator.config import settings
from loggator.db.session import AsyncSessionLocal
from loggator.tenancy.deps import resolve_effective_tenant_uuid

router = APIRouter(tags=["websocket"])

_WS_QUEUE_MAX = 200  # drop oldest when full to prevent unbounded memory growth


@dataclass
class _WsClient:
    """``tenant_filter`` None means receive events for all tenants (platform / dev)."""

    tenant_filter: frozenset[UUID] | None
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=_WS_QUEUE_MAX))


_clients: Dict[WebSocket, _WsClient] = {}


async def broadcast_tenant_event(tenant_id: UUID, event: dict) -> None:
    """Fan-out a tenant-scoped event to WebSocket clients subscribed to that tenant.

    Non-blocking: enqueues the serialised payload into each connection's queue.
    When a queue is full the oldest item is dropped to make room (slow-client
    back-pressure without blocking the broadcast caller).
    """
    payload = dict(event)
    payload.setdefault("tenant_id", str(tenant_id))
    text = json.dumps(payload, default=str)
    dead: list[WebSocket] = []
    for ws, reg in list(_clients.items()):
        if reg.tenant_filter is not None and tenant_id not in reg.tenant_filter:
            continue
        try:
            try:
                reg.queue.put_nowait(text)
            except asyncio.QueueFull:
                # Drop oldest to make room for the new event.
                try:
                    reg.queue.get_nowait()
                except asyncio.QueueEmpty:
                    pass
                reg.queue.put_nowait(text)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _clients.pop(ws, None)


async def _sender(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Drain the per-connection queue and send each frame to the WebSocket."""
    while True:
        text = await queue.get()
        try:
            await websocket.send_text(text)
        except Exception:
            break


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("access_token")
    q_tenant = websocket.query_params.get("tenant_id")
    iam = IAMClient()

    try:
        if settings.auth_disabled:
            if q_tenant:
                try:
                    tid = UUID(q_tenant.strip())
                    reg = _WsClient(tenant_filter=frozenset({tid}))
                except ValueError:
                    await websocket.close(code=4400)
                    return
            else:
                reg = _WsClient(tenant_filter=None)
        else:
            if not token:
                await websocket.close(code=4401)
                return
            user = await iam.verify_token(token)
            if user is None:
                await websocket.close(code=4401)
                return
            async with AsyncSessionLocal() as session:
                if "platform_admin" in (user.platform_roles or []):
                    reg = _WsClient(tenant_filter=None)
                else:
                    try:
                        tid = await resolve_effective_tenant_uuid(session, user, q_tenant)
                    except HTTPException:
                        await websocket.close(code=4403)
                        return
                    reg = _WsClient(tenant_filter=frozenset({tid}))
    except Exception:
        await websocket.close(code=1011)
        return

    _clients[websocket] = reg
    sender_task = asyncio.create_task(_sender(websocket, reg.queue))
    try:
        while True:
            await asyncio.sleep(30)
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "ping",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )
            )
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        sender_task.cancel()
        _clients.pop(websocket, None)
