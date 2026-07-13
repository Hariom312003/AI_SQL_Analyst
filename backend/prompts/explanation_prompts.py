"""Prompt templates for the Explanation Agent."""
from __future__ import annotations

EXPLANATION_SYSTEM_PROMPT = (
    "You are the Explanation Agent. Given the question, the SQL used, and a preview of "
    "the results, write a concise executive-style explanation: lead with the direct "
    "answer, then 1-3 supporting insights. Never just repeat raw numbers with no context."
)


def build_explanation_user_prompt(question: str, sql: str, columns: list[str], rows: list[dict]) -> str:
    preview = rows[:20]
    return f"Question: {question}\nSQL: {sql}\nColumns: {columns}\nRows (preview): {preview}"
