from fastapi import APIRouter
from pydantic import BaseModel
import httpx
from loggator.config import settings

router = APIRouter(tags=["status"])


class StatusResponse(BaseModel):
    ok: bool
    ollama_reachable: bool
    version: str = "0.1.0"


@router.get("/status", response_model=StatusResponse)
async def get_status():
    ollama_ok = False
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            ollama_ok = r.status_code == 200
    except Exception:
        pass

    return StatusResponse(ok=True, ollama_reachable=ollama_ok)


@router.get("/healthz")
async def healthz():
    return {"status": "ok"}
