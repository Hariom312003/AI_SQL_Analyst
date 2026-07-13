"""Common interface every LLM backend (Anthropic, offline fallback, ...) must
implement. Each method corresponds to one reasoning step in the agent
pipeline, rather than a single raw completion call -- this keeps prompts
co-located with whichever provider must fulfil them, and makes every agent
trivially testable against FakeLLMProvider with no network access."""
from __future__ import annotations

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    @abstractmethod
    def resolve_intent(self, question: str, history: list[dict]) -> dict:
        """Returns {"resolved_question": str, "intent_type": str, "filters": list[str]}."""

    @abstractmethod
    def generate_sql(self, question: str, schema_context: list[dict]) -> str:
        """Returns a single SELECT SQL statement."""

    @abstractmethod
    def repair_sql(self, question: str, schema_context: list[dict], bad_sql: str, error: str) -> str:
        """Returns a corrected SELECT SQL statement given the validation/execution error."""

    @abstractmethod
    def explain_results(self, question: str, sql: str, columns: list[str], rows: list[dict]) -> str:
        """Returns a natural-language explanation of the query results."""
