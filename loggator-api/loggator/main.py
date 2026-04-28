import structlog
import sentry_sdk
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from prometheus_fastapi_instrumentator import Instrumentator

from loggator.config import settings

# Auth module — IAM integration placeholder
from loggator.auth import dependencies as _auth  # noqa: F401 — imported for startup validation

# Initialize Sentry (no-op if SENTRY_DSN is empty)
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        environment=settings.sentry_environment,
        integrations=[StarletteIntegration(), FastApiIntegration()],
    )

from loggator.api.routes import summaries, anomalies, alerts, status, chat, logs
from loggator.api.routes import settings as settings_routes
from loggator.api.routes import schedule as schedule_routes
from loggator.api.routes import analysis_reports as analysis_reports_routes
from loggator.api.routes import health as health_routes
from loggator.api.routes import stats as stats_routes
from loggator.api.routes import system_events as system_events_routes
from loggator.api.routes import audit_log as audit_log_routes
from loggator.api import websocket
from loggator.observability.middleware import AuditLogMiddleware

log = structlog.get_logger()


def _real_client_ip(request: Request) -> str:
    """Read real client IP from X-Forwarded-For header (set by Traefik)."""
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.client.host  # fallback for direct connections


limiter = Limiter(key_func=_real_client_ip, default_limits=[settings.api_rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    from loggator.pipelines.scheduler import start_scheduler, stop_scheduler
    log.info("loggator.startup", host=settings.api_host, port=settings.api_port)
    start_scheduler()
    yield
    stop_scheduler()
    log.info("loggator.shutdown")


app = FastAPI(title="Loggator API", version="0.1.0", lifespan=lifespan)

# Expose /metrics endpoint for Prometheus scraping
Instrumentator().instrument(app).expose(app)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS — lock down to frontend origin in production
cors_origins = (
    ["*"] if settings.cors_allow_all
    else [settings.frontend_url]
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(AuditLogMiddleware)

app.include_router(status.router, prefix="/api/v1")
app.include_router(summaries.router, prefix="/api/v1")
app.include_router(anomalies.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(logs.router, prefix="/api/v1")
app.include_router(settings_routes.router, prefix="/api/v1")
app.include_router(schedule_routes.router, prefix="/api/v1")
app.include_router(analysis_reports_routes.router, prefix="/api/v1")
app.include_router(health_routes.router, prefix="/api/v1")
app.include_router(stats_routes.router, prefix="/api/v1")
app.include_router(system_events_routes.router, prefix="/api/v1")
app.include_router(audit_log_routes.router, prefix="/api/v1")
app.include_router(websocket.router)
