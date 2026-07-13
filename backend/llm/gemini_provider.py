"""Real LLM backend using Google's Gemini API via the `google-genai` SDK --
the unified SDK Google currently recommends for new projects (the older
`google-generativeai` package is deprecated; see
https://ai.google.dev/gemini-api/docs/libraries).

Set LLM_PROVIDER=gemini and GEMINI_API_KEY in .env to use this. Get a free
API key -- no credit card, no GCP project needed -- from Google AI Studio:
https://aistudio.google.com/app/apikey

Default model is gemini-2.5-flash: it's the stable, low-churn choice
Google's own SDK docs use in examples. A newer gemini-3.5-flash exists with
a more generous free-tier rate limit as of mid-2026 (roughly 15 req/min,
1,500 req/day for Flash-tier models, though check Google's current quota
page since this changes). Swap GEMINI_MODEL in .env if you want it --
nothing else in this file needs to change either way.
"""
from __future__ import annotations

from google import genai
from google.genai import types
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


class GeminiProvider(LLMProvider):
    def __init__(self, api_key: str | None = None, model: str | None = None):
        key = api_key or settings.gemini_api_key
        if not key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Get a free key (no credit card required) "
                "from https://aistudio.google.com/app/apikey and set it in .env, "
                "or set LLM_PROVIDER=fake / LLM_PROVIDER=anthropic instead."
            )
        self._client = genai.Client(api_key=key)
        self._model = model or settings.gemini_model

    def _complete(self, system: str, user: str) -> str:
        last_exc: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                response = self._client.models.generate_content(
                    model=self._model,
                    contents=user,
                    config=types.GenerateContentConfig(system_instruction=system, temperature=0.1),
                )
                return response.text or ""
            except Exception as exc:  # noqa: BLE001 - broad on purpose, we retry any failure
                last_exc = exc
                logger.warning("Gemini call failed (attempt {}): {}", attempt + 1, exc)
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
