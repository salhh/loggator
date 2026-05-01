from loggator.security.api_key_hash import hash_ingest_api_key
from loggator.config import settings


def test_hash_stable(monkeypatch):
    monkeypatch.setattr(settings, "api_key_pepper", type(settings.api_key_pepper)("test-pepper"))
    h1 = hash_ingest_api_key("lgk_abc")
    h2 = hash_ingest_api_key("lgk_abc")
    assert h1 == h2
    assert len(h1) == 64
