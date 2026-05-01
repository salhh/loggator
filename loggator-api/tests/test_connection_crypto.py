"""Field-level Fernet helpers for tenant connection secrets."""

from cryptography.fernet import Fernet

from loggator.config import settings
from loggator.security.connection_crypto import decrypt_secret, encrypt_secret


def test_encrypt_roundtrip_when_key_set(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(settings, "connection_secrets_fernet_key", type(settings.connection_secrets_fernet_key)(key))
    plain = "secret-password"
    enc = encrypt_secret(plain)
    assert enc != plain
    assert enc.startswith("enc:v1:")
    assert decrypt_secret(enc) == plain


def test_plaintext_when_no_key():
    assert encrypt_secret("hello") == "hello"
    assert decrypt_secret("hello") == "hello"
