import asyncio
from typing import Any

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
            self._model = ChatAnthropic(
                model=settings.anthropic_model,
                api_key=settings.anthropic_api_key.get_secret_value(),
                timeout=settings.llm_timeout,
            )
        elif provider == "openai":
            self._model = ChatOpenAI(
                model=settings.openai_model,
                api_key=settings.openai_api_key.get_secret_value(),
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
        prompt, schema = _PROMPT_MAP[prompt_type]
        chain = prompt | self._model.with_structured_output(schema).with_retry(stop_after_attempt=3)
        async with self._semaphore:
            log.debug("llm.generate", provider=settings.llm_provider, prompt_type=prompt_type)
            result = await chain.ainvoke({"logs": user_content})
            return result.model_dump()


llm_chain = LLMChain()
