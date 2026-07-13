"""SQL Agent -- generates a single PostgreSQL SELECT statement from the
resolved question and retrieved schema context."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.llm.base import LLMProvider


@instrumented("sql_agent")
def run(state: AgentState, llm: LLMProvider) -> AgentState:
    state["sql"] = llm.generate_sql(state["resolved_question"], state["schema_context"])
    state["repair_attempts"] = 0
    return state
