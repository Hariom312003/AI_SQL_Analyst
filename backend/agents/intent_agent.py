"""Intent Agent -- classifies the question and resolves conversational
follow-ups ('now only Electronics') into a fully self-contained question,
using the configured LLM provider."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.llm.base import LLMProvider


@instrumented("intent_agent")
def run(state: AgentState, llm: LLMProvider) -> AgentState:
    result = llm.resolve_intent(state["question"], state.get("history", []))
    state["resolved_question"] = result.get("resolved_question") or state["question"]
    state["intent"] = {
        "type": result.get("intent_type", "other"),
        "filters": result.get("filters", []),
    }
    return state
