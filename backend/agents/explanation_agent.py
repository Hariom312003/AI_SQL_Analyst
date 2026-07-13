"""Explanation Agent -- never returns raw numbers alone; always a short
executive-style explanation with the direct answer plus supporting insight."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.llm.base import LLMProvider


@instrumented("explanation_agent")
def run(state: AgentState, llm: LLMProvider) -> AgentState:
    if state.get("execution_error"):
        state["explanation"] = (
            f"I wasn't able to get a valid result after {state.get('repair_attempts', 0)} "
            f"repair attempt(s). Last error: {state['execution_error']}"
        )
        return state
    state["explanation"] = llm.explain_results(
        state["resolved_question"], state["sql"], state.get("result_columns", []), state.get("result_rows", [])
    )
    return state
