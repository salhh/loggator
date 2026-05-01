from datetime import datetime, timedelta, timezone
from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.session import get_session
from loggator.opensearch.client import get_opensearch_for_tenant, get_effective_index_pattern
from loggator.tenancy.deps import get_effective_tenant_id

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
    tenant_id: UUID = Depends(get_effective_tenant_id),
) -> StatsResponse:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    tid = str(tenant_id)

    total_summaries = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM summaries WHERE tenant_id = CAST(:tid AS uuid) AND created_at >= :s"
            ),
            {"tid": tid, "s": since},
        )
    ).scalar_one()

    total_anomalies = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM anomalies WHERE tenant_id = CAST(:tid AS uuid) AND detected_at >= :s"
            ),
            {"tid": tid, "s": since},
        )
    ).scalar_one()

    alerts_sent = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM alerts WHERE tenant_id = CAST(:tid AS uuid) "
                "AND created_at >= :s AND status = 'sent'"
            ),
            {"tid": tid, "s": since},
        )
    ).scalar_one()

    alerts_failed = (
        await session.execute(
            text(
                "SELECT COUNT(*) FROM alerts WHERE tenant_id = CAST(:tid AS uuid) "
                "AND created_at >= :s AND status = 'failed'"
            ),
            {"tid": tid, "s": since},
        )
    ).scalar_one()

    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM summaries WHERE tenant_id = CAST(:tid AS uuid) AND created_at >= :s GROUP BY d"
        ),
        {"tid": tid, "s": since},
    )
    daily_summaries: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (detected_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM anomalies WHERE tenant_id = CAST(:tid AS uuid) AND detected_at >= :s GROUP BY d"
        ),
        {"tid": tid, "s": since},
    )
    daily_anomalies: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    r = await session.execute(
        text(
            "SELECT (created_at AT TIME ZONE 'UTC')::date::text AS d, COUNT(*) "
            "FROM alerts WHERE tenant_id = CAST(:tid AS uuid) AND created_at >= :s GROUP BY d"
        ),
        {"tid": tid, "s": since},
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

    r = await session.execute(
        text(
            "SELECT severity, COUNT(*) FROM anomalies "
            "WHERE tenant_id = CAST(:tid AS uuid) AND detected_at >= :s GROUP BY severity"
        ),
        {"tid": tid, "s": since},
    )
    sev_map: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}
    anomalies_by_severity: dict[str, int] = {**sev_map}
    anomalies_by_severity.setdefault("low", 0)
    anomalies_by_severity.setdefault("medium", 0)
    anomalies_by_severity.setdefault("high", 0)

    r = await session.execute(
        text(
            "SELECT channel, COUNT(*) FROM alerts "
            "WHERE tenant_id = CAST(:tid AS uuid) AND created_at >= :s GROUP BY channel"
        ),
        {"tid": tid, "s": since},
    )
    alerts_by_channel: dict[str, int] = {row[0]: row[1] for row in r.fetchall()}

    log_volume: list[LogVolumeBucket] = []
    top_services: list[TopService] = []

    try:
        os_client = await get_opensearch_for_tenant(session, tenant_id)
        index_pattern = await get_effective_index_pattern(session, tenant_id)

        vol_resp = await os_client.search(
            index=index_pattern,
            body={
                "size": 0,
                "query": {"range": {"@timestamp": {"gte": since.strftime("%Y-%m-%dT%H:%M:%SZ")}}},
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

        lv_by_date = {b.date: b for b in log_volume}
        log_volume = []
        for i in range(days):
            d = (datetime.now(timezone.utc) - timedelta(days=days - 1 - i)).date().isoformat()
            log_volume.append(lv_by_date.get(d, LogVolumeBucket(date=d, error=0, warn=0, info=0)))

        svc_resp = await os_client.search(
            index=index_pattern,
            body={
                "size": 0,
                "query": {
                    "bool": {
                        "must": [
                            {"range": {"@timestamp": {"gte": since.strftime("%Y-%m-%dT%H:%M:%SZ")}}},
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
