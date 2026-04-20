import asyncio
import json
from datetime import datetime, timezone
from typing import Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])

_connections: Set[WebSocket] = set()


async def broadcast(event: dict) -> None:
    dead = set()
    for ws in _connections:
        try:
            await ws.send_text(json.dumps(event, default=str))
        except Exception:
            dead.add(ws)
    _connections.difference_update(dead)


@router.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await websocket.accept()
    _connections.add(websocket)
    try:
        while True:
            # Send periodic heartbeat; client messages are ignored
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({
                "type": "ping",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }))
    except WebSocketDisconnect:
        _connections.discard(websocket)
    except Exception:
        _connections.discard(websocket)
