from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings
from loggator.db.session import get_session

router = APIRouter(tags=["stats"])
log = structlog.get_logger()


class StatsTotals(BaseModel):
    summaries: int
    anomalies: int
    alerts_sent: int
    alerts_failed: int


class DailyBucket(BaseModel):
    date: str
    summaries: int
    anomalies: int
    alerts: int


class LogVolumeBucket(BaseModel):
    date: str
    error: int
    warn: int
    info: int


class TopService(BaseModel):
    service: str
    error_count: int


class StatsResponse(BaseModel):
    period_days: int
    totals: StatsTotals
    daily: list[DailyBucket]
    anomalies_by_severity: dict[str, int]
    alerts_by_channel: dict[str, int]
    log_volume: list[LogVolumeBucket]
    top_services: list[TopService]


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    days: int = Query(7, ge=1, le=30),
    session: AsyncSession = Depends(get_session),
) -> StatsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── PostgreSQL totals ──────────────────────────────────────────────────────
    total_summaries = (
        await session.execute(
            text("SELECT COUNT(*) FROM summaries WHERE created_at >= :s"), {"s": since}
        )
    ).scalar_one()

    total_anomalies = (
        await session.execute(
            text("SELECT COUNT(*) FROM anomalies WHERE detected_at >= :s"), {"s": since}
        )
    ).scalar_one()

    alerts_sent = (
        await session.execute(
            text("SELECT COUNT(*) FROM alerts WHERE created_at >= :s AND status = 'sent'"),
            {"s": since},
        )
    ).scalar_one()

    alerts_failed = (
        await session.execute(
            text("SELECT COUNT(*) FROM alerts WHERE created_at >= :s AND status = 'failed'"),
            {"s": since},
        )
    ).scalar_one()

    # ── Daily summaries ────────────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM summaries WHERE created_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_summaries: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (detected_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM anomalies WHERE detected_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_anomalies: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM alerts WHERE created_at >= :s GROUP BY d"
        ),
        {"s": since},
    )
    daily_alerts: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    daily: list[DailyBucket] = []
    for i in range(days):
        d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
        daily.append(
            DailyBucket(
                date=d,
                summaries=daily_summaries.get(d, 0),
                anomalies=daily_anomalies.get(d, 0),
                alerts=daily_alerts.get(d, 0),
            )
        )

    # ── Anomalies by severity ──────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT severity, COUNT(*) FROM anomalies WHERE detected_at >= :s GROUP BY severity"
        ),
        {"s": since},
    )
    sev_map: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}
    anomalies_by_severity = {
        "low": sev_map.get("low", 0),
        "medium": sev_map.get("medium", 0),
        "high": sev_map.get("high", 0),
    }

    # ── Alerts by channel ──────────────────────────────────────────────────────
    r = await session.execute(
        text(
            "SELECT channel, COUNT(*) FROM alerts WHERE created_at >= :s GROUP BY channel"
        ),
        {"s": since},
    )
    alerts_by_channel: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    # ── OpenSearch: log volume + top services (graceful degradation) ───────────
    log_volume: list[LogVolumeBucket] = []
    top_services: list[TopService] = []

    try:
        from loggator.opensearch.client import get_client

        os_client = get_client()

        vol_resp = await os_client.search(
            index=settings.opensearch_index_pattern,
            body={
                "size": 0,
                "query": {"range": {"@timestamp": {"gte": since.isoformat()}}},
                "aggs": {
                    "by_day": {
                        "date_histogram": {
                            "field": "@timestamp",
                            "calendar_interval": "day",
                            "format": "yyyy-MM-dd",
                        },
                        "aggs": {
                            "by_level": {
                                "terms": {"field": "level.keyword", "size": 10}
                            }
                        },
                    }
                },
            },
        )
        for bucket in vol_resp["aggregations"]["by_day"]["buckets"]:
            level_counts = {
                b["key"].upper(): b["doc_count"]
                for b in bucket["by_level"]["buckets"]
            }
            log_volume.append(
                LogVolumeBucket(
                    date=bucket["key_as_string"],
                    error=level_counts.get("ERROR", 0),
                    warn=level_counts.get("WARN", level_counts.get("WARNING", 0)),
                    info=level_counts.get("INFO", 0),
                )
            )

        svc_resp = await os_client.search(
            index=settings.opensearch_index_pattern,
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {"range": {"@timestamp": {"gte": since.isoformat()}}},
                            {"term": {"level.keyword": "ERROR"}},
                        ]
                    }
                },
                "aggs": {
                    "by_service": {
                        "terms": {"field": "service.keyword", "size": 10}
                    }
                },
            },
        )
        for bucket in svc_resp["aggregations"]["by_service"]["buckets"]:
            top_services.append(
                TopService(service=bucket["key"], error_count=bucket["doc_count"])
            )
    except Exception as exc:
        log.warning("stats.opensearch.unavailable", error=str(exc))

    return StatsResponse(
        period_days=days,
        totals=StatsTotals(
            summaries=total_summaries,
            anomalies=total_anomalies,
            alerts_sent=alerts_sent,
            alerts_failed=alerts_failed,
        ),
        daily=daily,
        anomalies_by_severity=anomalies_by_severity,
        alerts_by_channel=alerts_by_channel,
        log_volume=log_volume,
        top_services=top_services,
    )
