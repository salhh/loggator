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

# Prompts used only by the analysis (chat/analyze) pipeline
try:
    from loggator.llm.prompts import ANALYSIS_MAP_PROMPT, ANALYSIS_REDUCE_PROMPT
    from loggator.llm.schemas import AnalysisMapResult, AnalysisReduceResult
    _PROMPT_MAP["analysis_map"] = (ANALYSIS_MAP_PROMPT, AnalysisMapResult)
    _PROMPT_MAP["analysis_reduce"] = (ANALYSIS_REDUCE_PROMPT, AnalysisReduceResult)
except (ImportError, AttributeError):
    pass


class LLMChain:
    """
    Wraps a LangChain chat model with prompt routing and semaphore-gated concurrency.

    Pass `config` to build from a registry entry instead of the global settings:
        config = {"provider": "openai", "model": "gpt-4o", "api_key": "sk-...", "base_url": ""}
    """

    def __init__(self, config: dict | None = None) -> None:
        if config:
            provider = config.get("provider", "ollama")
            model = config.get("model", "")
            api_key = config.get("api_key", "")
            base_url = config.get("base_url", "") or None
            label = config.get("label", provider)
        else:
            provider = settings.llm_provider
            model = ""
            api_key = ""
            base_url = None
            label = provider

        self._provider = provider
        self._label = label

        if provider == "anthropic":
            key = api_key or (settings.anthropic_api_key.get_secret_value() if not config else "")
            if not key:
                raise ValueError("Anthropic provider requires an API key.")
            self._model = ChatAnthropic(
                model=model or settings.anthropic_model,
                api_key=key,
                timeout=settings.llm_timeout,
            )
        elif provider == "openai":
            key = api_key or (settings.openai_api_key.get_secret_value() if not config else "")
            if not key:
                raise ValueError("OpenAI provider requires an API key.")
            self._model = ChatOpenAI(
                model=model or settings.openai_model,
                api_key=key,
                base_url=base_url or (settings.openai_base_url or None),
                timeout=settings.llm_timeout,
            )
        else:  # ollama
            self._model = ChatOllama(
                model=model or settings.ollama_model,
                base_url=base_url or settings.ollama_base_url,
            )

        self._semaphore = asyncio.Semaphore(settings.llm_concurrency)

    async def generate(self, prompt_type: str, user_content: str) -> dict[str, Any]:
        if prompt_type not in _PROMPT_MAP:
            raise ValueError(f"Unknown prompt_type {prompt_type!r}. Valid: {list(_PROMPT_MAP)}")
        prompt, schema = _PROMPT_MAP[prompt_type]
        chain = prompt | self._model.with_structured_output(schema).with_retry(stop_after_attempt=3)
        async with self._semaphore:
            log.debug("llm.generate", provider=self._provider, label=self._label, prompt_type=prompt_type)
            try:
                result = await chain.ainvoke({"logs": user_content})
            except Exception as exc:
                log.error("llm.generate.failed", provider=self._provider, label=self._label,
                          prompt_type=prompt_type, error=str(exc))
                raise
            return result.model_dump()

    async def ainvoke(self, messages: list[BaseMessage]) -> str:
        async with self._semaphore:
            log.debug("llm.ainvoke", provider=self._provider, label=self._label)
            try:
                result = await self._model.ainvoke(messages)
            except Exception as exc:
                log.error("llm.ainvoke.failed", provider=self._provider, label=self._label, error=str(exc))
                raise
            content = result.content
        return content if isinstance(content, str) else str(content)


# Global singleton used by background pipelines (streaming, batch, scheduler)
llm_chain = LLMChain()
