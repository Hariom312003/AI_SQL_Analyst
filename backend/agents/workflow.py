"""Wires every agent into a single LangGraph StateGraph implementing the full
pipeline: Intent -> Schema Retrieval -> SQL Generation -> Validation ->
(repair loop) -> Execution -> (repair loop) -> Explanation -> Visualization.

Schema retrieval has no dedicated agent file (it's a thin, one-line call
into rag/retriever.py) so it's wired directly as a node here.
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.agents import (
    execution_agent,
    explanation_agent,
    intent_agent,
    repair_agent,
    sql_agent,
    validator_agent,
    visualization_agent,
)
from backend.agents.state import AgentState
from backend.config import get_settings
from backend.database.postgres import sync_engine
from backend.llm.base import LLMProvider
from backend.rag.retriever import retrieve_schema_context

settings = get_settings()


def _schema_retrieval_node(state: AgentState) -> AgentState:
    state["schema_context"] = retrieve_schema_context(state["resolved_question"])
    return state


def build_workflow(llm: LLMProvider):
    graph = StateGraph(AgentState)

    graph.add_node("intent", lambda s: intent_agent.run(s, llm))
    graph.add_node("schema_retrieval", _schema_retrieval_node)
    graph.add_node("sql_generation", lambda s: sql_agent.run(s, llm))
    graph.add_node("validation", validator_agent.run)
    graph.add_node("repair", lambda s: repair_agent.run(s, llm))
    graph.add_node("execution", lambda s: execution_agent.run(s, sync_engine))
    graph.add_node("explanation", lambda s: explanation_agent.run(s, llm))
    graph.add_node("visualization", visualization_agent.run)

    graph.set_entry_point("intent")
    graph.add_edge("intent", "schema_retrieval")
    graph.add_edge("schema_retrieval", "sql_generation")
    graph.add_edge("sql_generation", "validation")

    def after_validation(state: AgentState) -> str:
        if state["is_valid"]:
            return "execution"
        if state.get("repair_attempts", 0) >= settings.sql_repair_max_attempts:
            return "explanation"
        return "repair"

    graph.add_conditional_edges(
        "validation", after_validation,
        {"execution": "execution", "repair": "repair", "explanation": "explanation"},
    )
    graph.add_edge("repair", "validation")

    def after_execution(state: AgentState) -> str:
        if not state.get("execution_error"):
            return "explanation"
        if state.get("repair_attempts", 0) >= settings.sql_repair_max_attempts:
            return "explanation"
        return "repair"

    graph.add_conditional_edges(
        "execution", after_execution,
        {"explanation": "explanation", "repair": "repair"},
    )
    graph.add_edge("explanation", "visualization")
    graph.add_edge("visualization", END)

    return graph.compile()
