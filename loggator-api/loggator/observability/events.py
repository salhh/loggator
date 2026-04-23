"""
SystemEventWriter — persists platform diagnostic events to system_events.

De-duplication rule: if an identical (service + event_type, resolved_at IS NULL)
event exists within the last 5 minutes, skip the write. This applies only to
`error` and `disconnected` event types. Info events are always written.
"""
import structlog
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, select

from loggator.db.models import SystemEvent
from loggator.db.session import AsyncSessionLocal

log = structlog.get_logger()

# Only these event_types are subject to de-duplication
_DEDUP_EVENT_TYPES = frozenset({"error", "disconnected"})


class SystemEventWriter:
    async def write(
        self,
        service: str,
        event_type: str,
        severity: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        """
        Persist a platform event. Silently falls back to structlog if the DB is
        unavailable — the event is logged but never raises to the caller.
        """
        try:
            async with AsyncSessionLocal() as session:
                # De-duplication for error/disconnected events only
                if event_type in _DEDUP_EVENT_TYPES:
                    cutoff = datetime.now(timezone.utc) - timedelta(minutes=5)
                    result = await session.execute(
                        select(SystemEvent)
                        .where(
                            and_(
                                SystemEvent.service == service,
                                SystemEvent.event_type == event_type,
                                SystemEvent.resolved_at.is_(None),
                                SystemEvent.timestamp >= cutoff,
                            )
                        )
                        .limit(1)
                    )
                    if result.scalar_one_or_none() is not None:
                        log.debug(
                            "system_event.dedup_skipped",
                            service=service,
                            event_type=event_type,
                        )
                        return

                event = SystemEvent(
                    service=service,
                    event_type=event_type,
                    severity=severity,
                    message=message,
                    details=details,
                )
                session.add(event)
                await session.commit()
                log.debug(
                    "system_event.written",
                    service=service,
                    event_type=event_type,
                    severity=severity,
                )
        except Exception as exc:
            # DB unavailable — fall back to structlog only, never propagate
            log.error(
                "system_event.write_failed",
                service=service,
                event_type=event_type,
                error=str(exc),
            )


# Module-level singleton — import this wherever events need to be emitted
system_event_writer = SystemEventWriter()
