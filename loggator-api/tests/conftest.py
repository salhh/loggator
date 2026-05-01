"""
Root test conftest: stub all heavy third-party modules so tests run without
a live database, OpenSearch, or LLM stack installed.
Executes at collection time, before any test module is imported.
"""
import sys
from unittest.mock import MagicMock

# ── jose (JWT library) ───────────────────────────────────────────────────────
_jose = MagicMock()
_jose.exceptions = MagicMock()
_jose.exceptions.JOSEError = Exception
_jose.jwt = MagicMock()
sys.modules.setdefault("jose", _jose)
sys.modules.setdefault("jose.jwt", _jose.jwt)
sys.modules.setdefault("jose.exceptions", _jose.exceptions)

# ── OpenSearch / AWS ─────────────────────────────────────────────────────────
sys.modules.setdefault("opensearchpy", MagicMock())
sys.modules.setdefault("boto3", MagicMock())
sys.modules.setdefault("asyncpg", MagicMock())

# ── LLM / LangChain stack ────────────────────────────────────────────────────
for _mod in [
    "tiktoken",
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.language_models",
    "langchain_core.prompts",
    "langchain_core.output_parsers",
    "langchain_ollama",
    "langchain_anthropic",
    "langchain_openai",
]:
    sys.modules.setdefault(_mod, MagicMock())

# ── DB session (never connect to Postgres) ───────────────────────────────────
_session_mod = MagicMock()
_session_mod.AsyncSessionLocal = MagicMock()
sys.modules.setdefault("loggator.db.session", _session_mod)
