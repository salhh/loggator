# DEPRECATED: This client is kept only for embedding calls (nomic-embed-text via Ollama).
# LLM inference has moved to loggator.llm.chain. Do not use OllamaClient for new analysis work.
import asyncio
import json
from typing import Any

import httpx
import structlog

from loggator.config import settings

log = structlog.get_logger()

_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2}


class OllamaClient:
    def __init__(self, model: str | None = None, base_url: str | None = None):
        self.model = model or settings.ollama_model
        self.base_url = base_url or settings.ollama_base_url
        self._semaphore = asyncio.Semaphore(settings.ollama_concurrency)

    async def generate(self, system_prompt: str, user_content: str) -> dict[str, Any]:
        """Send a prompt + content to Ollama, return parsed JSON response."""
        payload = {
            "model": self.model,
            "prompt": f"{system_prompt}\n\nLogs:\n{user_content}",
            "format": "json",
            "stream": False,
        }

        async with self._semaphore:
            for attempt in range(1, 4):
                try:
                    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
                        r = await client.post(f"{self.base_url}/api/generate", json=payload)
                        r.raise_for_status()
                        raw = r.json().get("response", "{}")
                        return json.loads(raw)
                except (httpx.HTTPError, json.JSONDecodeError) as exc:
                    log.warning("ollama.generate.retry", attempt=attempt, error=str(exc))
                    if attempt == 3:
                        raise
                    await asyncio.sleep(2 ** attempt)

        return {}  # unreachable, satisfies type checker
