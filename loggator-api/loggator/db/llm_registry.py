"""
LLM configuration registry backed by the app_settings table.
Key format: "llm:<id>" — value: JSON blob.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import AppSettings

_PREFIX = "llm:"
_MASKED_KEYS = {"api_key"}


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


def _row_to_dict(row: AppSettings, masked: bool = True) -> dict:
    data = json.loads(row.value)
    data["id"] = row.key[len(_PREFIX):]
    data["updated_at"] = row.updated_at.isoformat() if row.updated_at else None
    return _mask(data) if masked else data


async def list_llms(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(AppSettings)
        .where(AppSettings.key.like(f"{_PREFIX}%"))
        .order_by(AppSettings.updated_at.desc())
    )
    return [_row_to_dict(r) for r in result.scalars()]


async def get_llm_raw(session: AsyncSession, id: str) -> dict:
    """Returns unmasked config — for internal use when building chains."""
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise LLMNotFound(id)
    return _row_to_dict(row, masked=False)


async def create_llm(session: AsyncSession, data: dict) -> dict:
    id = uuid.uuid4().hex[:8]
    payload = {k: v for k, v in data.items() if k not in ("id", "updated_at")}
    row = AppSettings(key=f"{_PREFIX}{id}", value=json.dumps(payload))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def update_llm(session: AsyncSession, id: str, data: dict) -> dict:
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise LLMNotFound(id)
    existing = json.loads(row.value)
    for k, v in data.items():
        if k not in ("id", "updated_at"):
            # Don't overwrite api_key if caller sent back the masked placeholder
            if k == "api_key" and isinstance(v, str) and v.endswith("****"):
                continue
            existing[k] = v
    row.value = json.dumps(existing)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def delete_llm(session: AsyncSession, id: str) -> None:
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise LLMNotFound(id)
    await session.delete(row)
    await session.commit()
