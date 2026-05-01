"""Deterministic hash for ingest API keys (pepper from settings)."""

import hashlib

from loggator.config import settings


def hash_ingest_api_key(raw: str) -> str:
    pepper = settings.api_key_pepper.get_secret_value()
    return hashlib.sha256(f"{pepper}:{raw}".encode()).hexdigest()
