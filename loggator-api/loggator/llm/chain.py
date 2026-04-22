import asyncio
from typing import Any

from langchain_core.messages import BaseMessage

import structlog
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI

from loggator.config import settings
from loggator.llm.prompts import ANOMALY_PROMPT, SUMMARY_MAP_PROMPT, SUMMARY_REDUCE_PROMPT
from loggator.llm.schemas import AnomalyResult, SummaryResult

log = structlog.get_logger()

_PROMPT_MAP = {
    "anomaly": (ANOMALY_PROMPT, AnomalyResult),
    "summary_map": (SUMMARY_MAP_PROMPT, SummaryResult),
    "summary_reduce": (SUMMARY_REDUCE_PROMPT, SummaryResult),
}


class LLMChain:
    def __init__(self) -> None:
        provider = settings.llm_provider
        if provider == "anthropic":
            key = settings.anthropic_api_key.get_secret_value()
            if not key:
                raise ValueError(
                    "LLM_PROVIDER is 'anthropic' but ANTHROPIC_API_KEY is not set. "
                    "Set the key or change LLM_PROVIDER to 'ollama'."
                )
            self._model = ChatAnthropic(
                model=settings.anthropic_model,
                api_key=key,
                timeout=settings.llm_timeout,
            )
        elif provider == "openai":
            key = settings.openai_api_key.get_secret_value()
            if not key:
                raise ValueError(
                    "LLM_PROVIDER is 'openai' but OPENAI_API_KEY is not set. "
                    "Set the key or change LLM_PROVIDER to 'ollama'."
                )
            self._model = ChatOpenAI(
                model=settings.openai_model,
                api_key=key,
                base_url=settings.openai_base_url or None,
                timeout=settings.llm_timeout,
            )
        else:  # ollama
            self._model = ChatOllama(
                model=settings.ollama_model,
                base_url=settings.ollama_base_url,
            )
        self._semaphore = asyncio.Semaphore(settings.llm_concurrency)

    async def generate(self, prompt_type: str, user_content: str) -> dict[str, Any]:
        """
        Run one LLM inference with structured output validation.
        prompt_type: 'anomaly' | 'summary_map' | 'summary_reduce'
        """
        if prompt_type not in _PROMPT_MAP:
            raise ValueError(f"Unknown prompt_type {prompt_type!r}. Valid: {list(_PROMPT_MAP)}")
        prompt, schema = _PROMPT_MAP[prompt_type]
        chain = prompt | self._model.with_structured_output(schema).with_retry(stop_after_attempt=3)
        async with self._semaphore:
            log.debug("llm.generate", provider=settings.llm_provider, prompt_type=prompt_type)
            try:
                result = await chain.ainvoke({"logs": user_content})
            except Exception as exc:
                log.error("llm.generate.failed", provider=settings.llm_provider,
                          prompt_type=prompt_type, error=str(exc))
                raise
            return result.model_dump()

    async def ainvoke(self, messages: list[BaseMessage]) -> str:
        """Free-form chat invocation — semaphore-gated, returns response text."""
        async with self._semaphore:
            log.debug("llm.ainvoke", provider=settings.llm_provider)
            try:
                result = await self._model.ainvoke(messages)
            except Exception as exc:
                log.error("llm.ainvoke.failed", provider=settings.llm_provider, error=str(exc))
                raise
            content = result.content
        return content if isinstance(content, str) else str(content)


llm_chain = LLMChain()
