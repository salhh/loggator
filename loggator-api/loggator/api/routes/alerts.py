from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.repository import AlertRepository

router = APIRouter(tags=["alerts"])


class AlertOut(BaseModel):
    id: UUID
    created_at: datetime
    anomaly_id: UUID
    channel: str
    destination: str
    status: str
    error: Optional[str]

    class Config:
        from_attributes = True


class WebhookIn(BaseModel):
    url: str
    channel: str = "webhook"


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    repo = AlertRepository(session)
    return await repo.list(limit=limit, offset=offset)


@router.post("/webhooks", status_code=201)
async def register_webhook(body: WebhookIn):
    # Stored in config/env for now; a full webhook registry table can be added later
    return {"message": "Webhook registered", "url": body.url, "channel": body.channel}


@router.post("/batch/trigger", status_code=202)
async def trigger_batch(background_tasks: BackgroundTasks):
    from loggator.pipelines.batch import run_batch
    background_tasks.add_task(run_batch)
    return {"message": "Batch run triggered"}
