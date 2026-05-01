"""Ingest API key verification (hashed at rest)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import TenantApiKey
from loggator.security.api_key_hash import hash_ingest_api_key


async def verify_ingest_api_key(session: AsyncSession, raw_key: str) -> UUID | None:
    if not raw_key.startswith("lgk_"):
        return None
    digest = hash_ingest_api_key(raw_key)
    result = await session.execute(
        select(TenantApiKey).where(
            TenantApiKey.key_hash == digest,
            TenantApiKey.revoked_at.is_(None),
        ).limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        return None
    scopes = row.scopes if isinstance(row.scopes, list) else []
    if "ingest" not in scopes:
        return None
    row.last_used_at = datetime.now(timezone.utc)
    await session.flush()
    return row.tenant_id
