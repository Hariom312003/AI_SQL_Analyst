"""Factory for selecting the configured LLM provider.

Resolution order: Gemini (free tier, recommended default for this project)
-> Anthropic (if you have a key and prefer it) -> FakeLLMProvider (always
works, zero setup, used automatically if no real provider is configured).
"""
from __future__ import annotations

from backend.config import get_settings
from backend.llm.anthropic_provider import AnthropicProvider
from backend.llm.base import LLMProvider
from backend.llm.fake_provider import FakeLLMProvider
from backend.llm.gemini_provider import GeminiProvider

settings = get_settings()


def get_llm_provider() -> LLMProvider:
    if settings.llm_provider == "gemini" and settings.gemini_api_key:
        return GeminiProvider()
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key:
        return AnthropicProvider()
    return FakeLLMProvider()
