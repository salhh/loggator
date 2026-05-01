from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.db.repository import AlertRepository
from loggator.tenancy.deps import get_effective_tenant_id

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


class TestAlertOut(BaseModel):
    ok: bool
    error: Optional[str] = None


class WebhookIn(BaseModel):
    url: str
    channel: str = "webhook"


@router.get("/alerts", response_model=list[AlertOut])
async def list_alerts(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    channel: Optional[str] = Query(None, description="Filter by channel: slack, email, telegram, webhook"),
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    return await AlertRepository(session, tenant_id).list(limit=limit, offset=offset, channel=channel)


@router.post("/alerts/test", response_model=TestAlertOut)
async def test_alert(
    channel: Literal["slack", "email", "telegram", "webhook"] = Query(..., description="Channel to test"),
):
    from loggator.alerts.dispatcher import dispatch_test
    try:
        ok, error = await dispatch_test(channel)
        return TestAlertOut(ok=ok, error=error if not ok else None)
    except Exception as exc:
        return TestAlertOut(ok=False, error=str(exc))


@router.post("/webhooks", status_code=201)
async def register_webhook(body: WebhookIn):
    return {"message": "Webhook registered", "url": body.url, "channel": body.channel}


@router.post("/batch/trigger", status_code=202)
async def trigger_batch(
    background_tasks: BackgroundTasks,
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    from loggator.pipelines.batch import run_batch
    background_tasks.add_task(run_batch, None, None, tenant_id)
    return {"message": "Batch run triggered"}
