"""
Conftest: stub out DB-level modules so tests don't need a live database.
Modules that connect at import time (loggator.db.session) are replaced with
lightweight mocks before any test module is imported.
"""
import sys
from unittest.mock import AsyncMock, MagicMock

# Stub loggator.db.session so create_async_engine is never called
mock_session_module = MagicMock()
mock_session_module.AsyncSessionLocal = MagicMock()
sys.modules.setdefault("loggator.db.session", mock_session_module)
