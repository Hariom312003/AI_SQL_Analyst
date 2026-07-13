"""Real LLM backend, using Anthropic's Messages API.

Set LLM_PROVIDER=anthropic and ANTHROPIC_API_KEY in .env to use this instead
of the offline FakeLLMProvider. Default model is claude-sonnet-5; override
via ANTHROPIC_MODEL (e.g. claude-opus-4-8 for tougher schemas, or
claude-haiku-4-5-20251001 to optimize for cost on high query volume).
"""
from __future__ import annotations

from anthropic import Anthropic
from loguru import logger

from backend.config import get_settings
from backend.llm.base import LLMProvider
from backend.llm.json_utils import extract_json
from backend.prompts.explanation_prompts import (
    EXPLANATION_SYSTEM_PROMPT,
    build_explanation_user_prompt,
)
from backend.prompts.intent_prompts import (
    INTENT_SYSTEM_PROMPT,
    build_intent_user_prompt,
)
from backend.prompts.sql_prompts import (
    SQL_GENERATION_SYSTEM_PROMPT,
    SQL_REPAIR_SYSTEM_PROMPT,
    build_sql_generation_user_prompt,
    build_sql_repair_user_prompt,
)

settings = get_settings()


class AnthropicProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._client = Anthropic(api_key=api_key or settings.anthropic_api_key)
        self._model = model or settings.anthropic_model

    def _complete(self, system: str, user: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=1500,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                return "".join(block.text for block in response.content if block.type == "text")
            except Exception as exc:  # noqa: BLE001 - broad on purpose, we retry any failure
                last_exc = exc
                logger.warning("Anthropic call failed (attempt {}): {}", attempt + 1, exc)
        assert last_exc is not None
        raise last_exc

    def _complete_json(self, system: str, user: str) -> dict:
        strict_system = system + "\n\nRespond with ONLY valid JSON, no markdown fences, no commentary."
        raw = self._complete(strict_system, user)
        return extract_json(raw)

    def resolve_intent(self, question: str, history: list[dict]) -> dict:
        history_text = "\n".join(f"{h['role']}: {h['content']}" for h in history[-6:])
        return self._complete_json(INTENT_SYSTEM_PROMPT, build_intent_user_prompt(question, history_text))

    def generate_sql(self, question: str, schema_context: list[dict]) -> str:
        user = build_sql_generation_user_prompt(question, schema_context)
        return self._complete_json(SQL_GENERATION_SYSTEM_PROMPT, user)["sql"]

    def repair_sql(self, question: str, schema_context: list[dict], bad_sql: str, error: str) -> str:
        user = build_sql_repair_user_prompt(question, schema_context, bad_sql, error)
        return self._complete_json(SQL_REPAIR_SYSTEM_PROMPT, user)["sql"]

    def explain_results(self, question: str, sql: str, columns: list[str], rows: list[dict]) -> str:
        user = build_explanation_user_prompt(question, sql, columns, rows)
        return self._complete(EXPLANATION_SYSTEM_PROMPT, user)
