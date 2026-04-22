import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from loggator.config import settings
from loggator.api.routes import summaries, anomalies, alerts, status, chat, logs
from loggator.api.routes import settings as settings_routes
from loggator.api.routes import schedule as schedule_routes
from loggator.api.routes import analysis_reports as analysis_reports_routes
from loggator.api.routes import health as health_routes
from loggator.api.routes import stats as stats_routes
from loggator.api.routes import llms as llms_routes
from loggator.api.routes import alert_channels as alert_channels_routes
from loggator.api import websocket

log = structlog.get_logger()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.api_rate_limit])


@asynccontextmanager
async def lifespan(app: FastAPI):
    from loggator.pipelines.scheduler import start_scheduler, stop_scheduler
    log.info("loggator.startup", host=settings.api_host, port=settings.api_port)
    start_scheduler()
    yield
    stop_scheduler()
    log.info("loggator.shutdown")


app = FastAPI(title="Loggator API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
app.include_router(llms_routes.router, prefix="/api/v1")
app.include_router(alert_channels_routes.router, prefix="/api/v1")
app.include_router(websocket.router)
