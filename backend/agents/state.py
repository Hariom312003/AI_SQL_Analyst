"""Shared state passed between every node in the LangGraph workflow."""
from __future__ import annotations

from typing import Optional, TypedDict


class AgentState(TypedDict, total=False):
    conversation_id: Optional[str]
    history: list[dict]

    question: str
    resolved_question: str
    intent: dict

    schema_context: list[dict]

    sql: str
    is_valid: bool
    validation_errors: list[str]
    repair_attempts: int
    execution_error: Optional[str]

    result_columns: list[str]
    result_rows: list[dict]
    row_count: int

    explanation: str
    chart_spec: dict
