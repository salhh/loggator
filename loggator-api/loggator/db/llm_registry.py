"""
LLM configuration registry backed by the app_settings table.
Key format: "t:{tenant_id}:llm:{id}" — value: JSON blob.
"""
import json
import uuid
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import AppSettings

_MASKED_KEYS = {"api_key"}


def _prefix(tenant_id: UUID) -> str:
    return f"t:{tenant_id}:llm:"


def _row_key(tenant_id: UUID, id_: str) -> str:
    return f"{_prefix(tenant_id)}{id_}"


class LLMNotFound(Exception):
    pass


def _mask(data: dict) -> dict:
    out = dict(data)
    for k in _MASKED_KEYS:
        v = out.get(k) or ""
        if v and len(v) > 4:
            out[k] = v[:4] + "****"
        elif v:
            out[k] = "****"
    return out


def _row_to_dict(row: AppSettings, tenant_id: UUID, masked: bool = True) -> dict:
    data = json.loads(row.value)
    pfx = _prefix(tenant_id)
    data["id"] = row.key[len(pfx):]
    data["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return _mask(data) if masked else data


async def list_llms(session: AsyncSession, tenant_id: UUID) -> list[dict]:
    pfx = _prefix(tenant_id)
    result = await session.execute(
        select(AppSettings)
        .where(AppSettings.key.like(f"{pfx}%"))
        .order_by(AppSettings.updated_at.desc())
    )
    return [_row_to_dict(r, tenant_id) for r in result.scalars()]


async def get_llm_raw(session: AsyncSession, tenant_id: UUID, id: str) -> dict:
    """Returns unmasked config — for internal use when building chains."""
    row = await session.get(AppSettings, _row_key(tenant_id, id))
    if not row:
        raise LLMNotFound(id)
    return _row_to_dict(row, tenant_id, masked=False)


async def create_llm(session: AsyncSession, tenant_id: UUID, data: dict) -> dict:
    id = uuid.uuid4().hex[:8]
    payload = {k: v for k, v in data.items() if k not in ("id", "updated_at")}
    row = AppSettings(key=_row_key(tenant_id, id), value=json.dumps(payload))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row, tenant_id)


async def update_llm(session: AsyncSession, tenant_id: UUID, id: str, data: dict) -> dict:
    row = await session.get(AppSettings, _row_key(tenant_id, id))
    if not row:
        raise LLMNotFound(id)
    existing = json.loads(row.value)
    for k, v in data.items():
        if k not in ("id", "updated_at"):
            if k == "api_key" and isinstance(v, str) and v.endswith("****"):
                continue
            existing[k] = v
    row.value = json.dumps(existing)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row, tenant_id)


async def delete_llm(session: AsyncSession, tenant_id: UUID, id: str) -> None:
    row = await session.get(AppSettings, _row_key(tenant_id, id))
    if not row:
        raise LLMNotFound(id)
    await session.delete(row)
    await session.commit()
