from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.models import TenantConnection
from loggator.db.session import get_session
from loggator.opensearch.client import get_effective_index_pattern
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
    result = await session.execute(
        select(TenantConnection).where(TenantConnection.tenant_id == tenant_id).limit(1)
    )
    conn = result.scalar_one_or_none()

    configured = bool(conn and conn.opensearch_host and str(conn.opensearch_host).strip())
    index_pattern = await get_effective_index_pattern(session, tenant_id)

    # Render a redacted "effective" view (never return passwords/api keys).
    host = (conn.opensearch_host if conn and conn.opensearch_host else settings.opensearch_host) or ""
    port = int(conn.opensearch_port) if conn and conn.opensearch_port is not None else int(settings.opensearch_port)
    auth_type = (conn.opensearch_auth_type if conn and conn.opensearch_auth_type else settings.opensearch_auth_type) or "none"
    use_ssl = bool(conn.opensearch_use_ssl) if conn and conn.opensearch_use_ssl is not None else bool(settings.opensearch_use_ssl)
    verify_certs = bool(conn.opensearch_verify_certs) if conn and conn.opensearch_verify_certs is not None else bool(settings.opensearch_verify_certs)

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

