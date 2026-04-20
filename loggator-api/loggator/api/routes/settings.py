import os
import re
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["settings"])

_ENV_PATH = Path(__file__).parent.parent.parent.parent / ".env.dev"
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


@router.get("/settings", response_model=SettingsOut)
async def get_settings():
    if not _ENV_PATH.exists():
        raise HTTPException(status_code=404, detail=f".env file not found at {_ENV_PATH}")
    raw = _ENV_PATH.read_text(encoding="utf-8")
    parsed = _parse_env(raw)
    masked = {k: _mask(k, v) for k, v in parsed.items()}
    return SettingsOut(settings=masked, env_file=str(_ENV_PATH))


@router.put("/settings", response_model=SettingsOut)
async def update_settings(body: SettingsIn):
    if not _ENV_PATH.exists():
        raise HTTPException(status_code=404, detail=f".env file not found at {_ENV_PATH}")

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

    parsed = _parse_env("\n".join(lines))
    masked = {k: _mask(k, v) for k, v in parsed.items()}
    return SettingsOut(settings=masked, env_file=str(_ENV_PATH))
