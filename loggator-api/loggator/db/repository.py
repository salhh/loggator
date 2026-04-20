from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import Alert, Anomaly, Checkpoint, Summary


class SummaryRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, summary: Summary) -> Summary:
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
        q = select(Summary).order_by(Summary.created_at.desc())
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
        result = await self.session.execute(select(Summary).where(Summary.id == id))
        return result.scalar_one_or_none()

    async def get_latest(self) -> Optional[Summary]:
        result = await self.session.execute(select(Summary).order_by(Summary.created_at.desc()).limit(1))
        return result.scalar_one_or_none()


class AnomalyRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, anomaly: Anomaly) -> Anomaly:
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
        q = select(Anomaly).order_by(Anomaly.detected_at.desc())
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
        result = await self.session.execute(select(Anomaly).where(Anomaly.id == id))
        return result.scalar_one_or_none()

    async def mark_alerted(self, id: UUID) -> None:
        await self.session.execute(update(Anomaly).where(Anomaly.id == id).values(alerted=True))
        await self.session.commit()


class AlertRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, alert: Alert) -> Alert:
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def list(self, limit: int = 50, offset: int = 0) -> list[Alert]:
        q = select(Alert).order_by(Alert.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(q)
        return list(result.scalars().all())


class CheckpointRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, index_pattern: str) -> Optional[Checkpoint]:
        result = await self.session.execute(
            select(Checkpoint).where(Checkpoint.index_pattern == index_pattern)
        )
        return result.scalar_one_or_none()

    async def save(self, checkpoint: Checkpoint) -> Checkpoint:
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
                index_pattern=index_pattern,
                last_sort=last_sort,
                last_seen_at=last_seen_at,
            )
            self.session.add(checkpoint)
            await self.session.commit()
