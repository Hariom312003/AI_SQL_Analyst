"""Repair Agent -- reads the validation or execution error, consults the
schema, and asks the LLM for a corrected statement (module: SQL
Self-Correction)."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.llm.base import LLMProvider


@instrumented("repair_agent")
def run(state: AgentState, llm: LLMProvider) -> AgentState:
    error_text = (
        "; ".join(state.get("validation_errors") or [])
        or state.get("execution_error")
        or "Unknown error"
    )
    state["sql"] = llm.repair_sql(state["resolved_question"], state["schema_context"], state["sql"], error_text)
    state["repair_attempts"] = state.get("repair_attempts", 0) + 1
    state["execution_error"] = None
    return state
