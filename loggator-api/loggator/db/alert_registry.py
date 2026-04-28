"""
Alert channel registry backed by the app_settings table.
Key format: "alert_channel:<id>" — value: JSON blob.
"""
import json
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.db.models import AppSettings

_PREFIX = "alert_channel:"

# Sensitive fields to mask per channel type
_MASKED: dict[str, set[str]] = {
    "slack":    {"webhook_url"},
    "telegram": {"bot_token"},
    "email":    set(),
    "webhook":  set(),
}


class AlertChannelNotFound(Exception):
    pass


def _mask_config(channel_type: str, config: dict) -> dict:
    out = dict(config)
    for k in _MASKED.get(channel_type, set()):
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
    if masked:
        data["config"] = _mask_config(data.get("type", ""), data.get("config", {}))
    return data


async def list_channels(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(AppSettings)
        .where(AppSettings.key.like(f"{_PREFIX}%"))
        .order_by(AppSettings.updated_at.desc())
    )
    return [_row_to_dict(r) for r in result.scalars()]


async def list_enabled_channels_raw(session: AsyncSession) -> list[dict]:
    """Returns unmasked configs for all enabled channels — used by the dispatcher."""
    result = await session.execute(
        select(AppSettings).where(AppSettings.key.like(f"{_PREFIX}%"))
    )
    return [
        _row_to_dict(r, masked=False)
        for r in result.scalars()
        if json.loads(r.value).get("enabled", True)
    ]


async def get_channel_raw(session: AsyncSession, id: str) -> dict:
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise AlertChannelNotFound(id)
    return _row_to_dict(row, masked=False)


async def create_channel(session: AsyncSession, data: dict) -> dict:
    id = uuid.uuid4().hex[:8]
    payload = {k: v for k, v in data.items() if k not in ("id", "updated_at")}
    row = AppSettings(key=f"{_PREFIX}{id}", value=json.dumps(payload))
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def update_channel(session: AsyncSession, id: str, data: dict) -> dict:
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise AlertChannelNotFound(id)
    existing = json.loads(row.value)
    channel_type = data.get("type") or existing.get("type", "")
    for k, v in data.items():
        if k in ("id", "updated_at"):
            continue
        # Don't overwrite secrets if the caller sent back the masked placeholder
        if k == "config" and isinstance(v, dict):
            merged = dict(existing.get("config", {}))
            for ck, cv in v.items():
                if ck in _MASKED.get(channel_type, set()) and isinstance(cv, str) and cv.endswith("****"):
                    continue
                merged[ck] = cv
            existing["config"] = merged
        else:
            existing[k] = v
    row.value = json.dumps(existing)
    await session.commit()
    await session.refresh(row)
    return _row_to_dict(row)


async def delete_channel(session: AsyncSession, id: str) -> None:
    row = await session.get(AppSettings, f"{_PREFIX}{id}")
    if not row:
        raise AlertChannelNotFound(id)
    await session.delete(row)
    await session.commit()
