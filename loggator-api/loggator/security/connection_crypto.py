"""Encrypt sensitive TenantConnection fields at rest (Fernet)."""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from loggator.config import settings

_ENC_PREFIX = "enc:v1:"


def _fernet() -> Fernet | None:
    key = settings.connection_secrets_fernet_key.get_secret_value().strip()
    if not key:
        return None
    return Fernet(key.encode("utf-8"))


def encrypt_secret(plain: str | None) -> str | None:
    if plain is None or plain == "":
        return plain
    f = _fernet()
    if f is None:
        return plain
    token = f.encrypt(plain.encode("utf-8"))
    return _ENC_PREFIX + token.decode("ascii")


def decrypt_secret(stored: str | None) -> str | None:
    if stored is None or stored == "":
        return stored
    if not stored.startswith(_ENC_PREFIX):
        return stored
    f = _fernet()
    if f is None:
        return stored
    raw = stored[len(_ENC_PREFIX) :].encode("ascii")
    try:
        return f.decrypt(raw).decode("utf-8")
    except InvalidToken:
        return stored
