from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Alert, Anomaly, Checkpoint, Summary, ScheduledAnalysis


class SummaryRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, summary: Summary) -> Summary:
        if summary.tenant_id is None:
            summary.tenant_id = self.tenant_id
        self.session.add(summary)
        await self.session.commit()
        await self.session.refresh(summary)
        return summary

    async def list(
        self,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        index_pattern: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Summary]:
        q = (
            select(Summary)
            .where(Summary.tenant_id == self.tenant_id)
            .order_by(Summary.created_at.desc())
        )
        if from_ts:
            q = q.where(Summary.created_at >= from_ts)
        if to_ts:
            q = q.where(Summary.created_at <= to_ts)
        if index_pattern:
            q = q.where(Summary.index_pattern == index_pattern)
        q = q.limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get(self, id: UUID) -> Optional[Summary]:
        result = await self.session.execute(
            select(Summary).where(Summary.id == id, Summary.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def get_latest(self) -> Optional[Summary]:
        result = await self.session.execute(
            select(Summary)
            .where(Summary.tenant_id == self.tenant_id)
            .order_by(Summary.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


class AnomalyRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, anomaly: Anomaly) -> Anomaly:
        if anomaly.tenant_id is None:
            anomaly.tenant_id = self.tenant_id
        self.session.add(anomaly)
        await self.session.commit()
        await self.session.refresh(anomaly)
        return anomaly

    async def list(
        self,
        severity: Optional[list[str]] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        index_pattern: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Anomaly]:
        q = (
            select(Anomaly)
            .where(Anomaly.tenant_id == self.tenant_id)
            .order_by(Anomaly.detected_at.desc())
        )
        if severity:
            q = q.where(Anomaly.severity.in_(severity))
        if from_ts:
            q = q.where(Anomaly.detected_at >= from_ts)
        if to_ts:
            q = q.where(Anomaly.detected_at <= to_ts)
        if index_pattern:
            q = q.where(Anomaly.index_pattern == index_pattern)
        q = q.limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())

    async def get(self, id: UUID) -> Optional[Anomaly]:
        result = await self.session.execute(
            select(Anomaly).where(Anomaly.id == id, Anomaly.tenant_id == self.tenant_id)
        )
        return result.scalar_one_or_none()

    async def mark_alerted(self, id: UUID) -> None:
        await self.session.execute(
            update(Anomaly)
            .where(Anomaly.id == id, Anomaly.tenant_id == self.tenant_id)
            .values(alerted=True)
        )
        await self.session.commit()


class AlertRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, alert: Alert) -> Alert:
        if alert.tenant_id is None:
            alert.tenant_id = self.tenant_id
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def list(self, limit: int = 50, offset: int = 0, channel: str | None = None) -> list[Alert]:
        q = (
            select(Alert)
            .where(Alert.tenant_id == self.tenant_id)
            .order_by(Alert.created_at.desc())
        )
        if channel:
            q = q.where(Alert.channel == channel)
        q = q.limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())


class CheckpointRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def get(self, index_pattern: str) -> Optional[Checkpoint]:
        result = await self.session.execute(
            select(Checkpoint).where(
                Checkpoint.index_pattern == index_pattern,
                Checkpoint.tenant_id == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
        if checkpoint.tenant_id is None:
            checkpoint.tenant_id = self.tenant_id
        self.session.add(checkpoint)
        await self.session.commit()
        await self.session.refresh(checkpoint)
        return checkpoint

    async def upsert(self, index_pattern: str, last_sort: list, last_seen_at: datetime) -> None:
        existing = await self.get(index_pattern)
        if existing:
            existing.last_sort = last_sort
            existing.last_seen_at = last_seen_at
            await self.session.commit()
        else:
            checkpoint = Checkpoint(
                tenant_id=self.tenant_id,
                index_pattern=index_pattern,
                last_sort=last_sort,
                last_seen_at=last_seen_at,
            )
            self.session.add(checkpoint)
            await self.session.commit()


class ScheduledAnalysisRepository:
    def __init__(self, session: AsyncSession, tenant_id: UUID):
        self.session = session
        self.tenant_id = tenant_id

    async def save(self, record: ScheduledAnalysis) -> ScheduledAnalysis:
        if record.tenant_id is None:
            record.tenant_id = self.tenant_id
        self.session.add(record)
        await self.session.commit()
        await self.session.refresh(record)
        return record

    async def list(
        self,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        index_pattern: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ScheduledAnalysis]:
        q = (
            select(ScheduledAnalysis)
            .where(ScheduledAnalysis.tenant_id == self.tenant_id)
            .order_by(ScheduledAnalysis.created_at.desc())
        )
        if from_ts:
            q = q.where(ScheduledAnalysis.created_at >= from_ts)
        if to_ts:
            q = q.where(ScheduledAnalysis.created_at <= to_ts)
        if index_pattern:
            q = q.where(ScheduledAnalysis.index_pattern == index_pattern)
        result = await self.session.execute(q.limit(limit).offset(offset))
        return list(result.scalars().all())

    async def get(self, id: UUID) -> Optional[ScheduledAnalysis]:
        result = await self.session.execute(
            select(ScheduledAnalysis).where(
                ScheduledAnalysis.id == id,
                ScheduledAnalysis.tenant_id == self.tenant_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_latest(self) -> Optional[ScheduledAnalysis]:
        result = await self.session.execute(
            select(ScheduledAnalysis)
            .where(ScheduledAnalysis.tenant_id == self.tenant_id)
            .order_by(ScheduledAnalysis.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def find_by_window(
        self,
        from_ts: datetime,
        to_ts: datetime,
        tolerance_minutes: int = 2,
    ) -> Optional[ScheduledAnalysis]:
        """Return an existing record covering this window (used for deduplication)."""
        from datetime import timedelta

        tol = timedelta(minutes=tolerance_minutes)
        result = await self.session.execute(
            select(ScheduledAnalysis)
            .where(
                ScheduledAnalysis.tenant_id == self.tenant_id,
                ScheduledAnalysis.window_start >= from_ts - tol,
                ScheduledAnalysis.window_end <= to_ts + tol,
            )
            .order_by(ScheduledAnalysis.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
