from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session
from loggator.opensearch.client import get_effective_index_pattern, get_effective_opensearch_display
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(tags=["runtime"])


class OpenSearchRuntime(BaseModel):
    configured: bool
    host: str
    port: int
    auth_type: str
    index_pattern: str
    use_ssl: bool
    verify_certs: bool


class LLMRuntime(BaseModel):
    provider: str
    base_url: str
    model: str
    embed_model: str


class ScheduleRuntime(BaseModel):
    enabled: bool
    interval_minutes: int
    window_minutes: int
    next_run_at: Optional[str] = None


class RuntimeOut(BaseModel):
    tenant_id: UUID
    opensearch: OpenSearchRuntime
    llm: LLMRuntime
    schedule: ScheduleRuntime


@router.get("/runtime", response_model=RuntimeOut)
async def get_runtime(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    eff = await get_effective_opensearch_display(session, tenant_id)
    configured = bool(eff["configured"])
    index_pattern = await get_effective_index_pattern(session, tenant_id)

    host = str(eff["host"])
    port = int(eff["port"])
    auth_type = str(eff["auth_type"])
    use_ssl = bool(eff["use_ssl"])
    verify_certs = bool(eff["verify_certs"])

    # Scheduler next run (best-effort).
    next_run_at = None
    try:
        from loggator.pipelines.scheduler import get_scheduler

        sched = get_scheduler()
        if sched and sched.running:
            job = sched.get_job("scheduled_analysis")
            if job and job.next_run_time:
                next_run_at = job.next_run_time.isoformat()
    except Exception:
        pass

    return RuntimeOut(
        tenant_id=tenant_id,
        opensearch=OpenSearchRuntime(
            configured=configured,
            host=str(host),
            port=port,
            auth_type=str(auth_type),
            index_pattern=str(index_pattern),
            use_ssl=use_ssl,
            verify_certs=verify_certs,
        ),
        llm=LLMRuntime(
            provider=settings.llm_provider,
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
            embed_model=settings.ollama_embed_model,
        ),
        schedule=ScheduleRuntime(
            enabled=bool(settings.analysis_enabled),
            interval_minutes=int(settings.analysis_interval_minutes),
            window_minutes=int(settings.analysis_window_minutes),
            next_run_at=next_run_at,
        ),
    )

