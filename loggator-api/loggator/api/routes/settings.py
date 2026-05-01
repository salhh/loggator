import os
import re
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from loggator.config import settings as _settings
from loggator.db.session import get_session
from loggator.opensearch.client import get_effective_index_pattern, get_effective_opensearch_display
from loggator.tenancy.deps import get_effective_tenant_id

router = APIRouter(tags=["settings"])

_ENV_PATH = Path(os.environ.get("ENV_FILE_PATH", Path(__file__).parent.parent.parent.parent / ".env"))
_SECRET_KEYS = {"DATABASE_URL", "OPENSEARCH_PASSWORD", "OPENSEARCH_API_KEY", "SLACK_WEBHOOK_URL", "SMTP_PASSWORD"}


def _parse_env(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def _mask(key: str, value: str) -> str:
    if key in _SECRET_KEYS and value:
        return value[:4] + "****"
    return value


class SettingsOut(BaseModel):
    settings: dict[str, str]
    env_file: str


class SettingsIn(BaseModel):
    updates: dict[str, str]

class EffectiveSettingsOut(BaseModel):
    tenant_id: UUID
    opensearch: dict[str, str | int | bool]
    llm: dict[str, str | int | bool]
    schedule: dict[str, str | int | bool]

@router.get("/settings", response_model=SettingsOut)
async def get_settings():
    if not _ENV_PATH.exists():
        return SettingsOut(settings={}, env_file=str(_ENV_PATH))
    raw = _ENV_PATH.read_text(encoding="utf-8")
    parsed = _parse_env(raw)
    masked = {k: _mask(k, v) for k, v in parsed.items()}
    return SettingsOut(settings=masked, env_file=str(_ENV_PATH))


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsIn):
    if not _ENV_PATH.exists():
        _ENV_PATH.write_text("", encoding="utf-8")

    raw = _ENV_PATH.read_text(encoding="utf-8")
    lines = raw.splitlines()

    for key, new_value in body.updates.items():
        found = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith(f"{key}=") or stripped.startswith(f"{key} ="):
                lines[i] = f"{key}={new_value}"
                found = True
                break
        if not found:
            lines.append(f"{key}={new_value}")

    _ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Update the in-memory settings singleton so changes take effect immediately.
    # Write directly into __dict__ to bypass Pydantic v2's descriptor layer.
    from loggator.config import settings as _settings
    for key, new_value in body.updates.items():
        field_name = key.lower()
        if field_name in _settings.model_fields:
            field = _settings.model_fields[field_name]
            try:
                if field.annotation is int:
                    coerced = int(new_value)
                elif field.annotation is bool:
                    coerced = new_value.lower() in ("true", "1", "yes")
                else:
                    coerced = new_value
                _settings.__dict__[field_name] = coerced
            except Exception:
                pass  # best-effort; file write already succeeded

    parsed = _parse_env("\n".join(lines))
    masked = {k: _mask(k, v) for k, v in parsed.items()}
    return SettingsOut(settings=masked, env_file=str(_ENV_PATH))


@router.get("/settings/effective", response_model=EffectiveSettingsOut)
async def get_effective_settings(
    session: AsyncSession = Depends(get_session),
    tenant_id: UUID = Depends(get_effective_tenant_id),
):
    """
    Tenant-scoped effective settings (redacted).

    This is intended for UI/runtime visibility. It merges tenant connection values with
    process-wide defaults without exposing secrets (passwords, API keys).
    """
    index_pattern = await get_effective_index_pattern(session, tenant_id)
    eff = await get_effective_opensearch_display(session, tenant_id)

    opensearch = {
        "configured": bool(eff["configured"]),
        "source": eff["source"],
        "provider": eff["provider"],
        "host": str(eff["host"]),
        "port": int(eff["port"]),
        "auth_type": str(eff["auth_type"]),
        "use_ssl": bool(eff["use_ssl"]),
        "verify_certs": bool(eff["verify_certs"]),
        "index_pattern": str(index_pattern),
    }

    llm = {
        "provider": _settings.llm_provider,
        "ollama_base_url": _settings.ollama_base_url,
        "ollama_model": _settings.ollama_model,
        "ollama_embed_model": _settings.ollama_embed_model,
        "llm_timeout": int(_settings.llm_timeout),
        "llm_concurrency": int(_settings.llm_concurrency),
    }

    schedule = {
        "analysis_enabled": bool(_settings.analysis_enabled),
        "analysis_interval_minutes": int(_settings.analysis_interval_minutes),
        "analysis_window_minutes": int(_settings.analysis_window_minutes),
    }

    return EffectiveSettingsOut(
        tenant_id=tenant_id,
        opensearch=opensearch,
        llm=llm,
        schedule=schedule,
    )
