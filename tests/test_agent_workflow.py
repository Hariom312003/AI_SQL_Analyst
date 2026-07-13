"""End-to-end smoke test for the compiled LangGraph workflow.

Uses FakeLLMProvider (no network) with schema retrieval, live-schema lookup,
and SQL execution monkeypatched out -- this test needs no Postgres, no
ChromaDB, and no API key, so it runs the same way in CI as on a laptop.
Patch targets matter here: each name is patched where it's *looked up*
(the importing module's namespace), not where it's defined.
"""
from __future__ import annotations

from unittest.mock import patch

from backend.agents.workflow import build_workflow
from backend.llm.fake_provider import FakeLLMProvider

FAKE_SCHEMA_CONTEXT = [
    {"text": "Table 'orders'.", "metadata": {"type": "table", "table_name": "orders"}},
    {
        "text": "Column 'product' in table 'orders'. Product name.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "product",
            "sql_type": "Text", "sample_values": ["Laptop", "Mouse"],
        },
    },
    {
        "text": "Column 'total_price' in table 'orders'. Represents sale revenue.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "total_price",
            "sql_type": "Float", "sample_values": [],
        },
    },
]


@patch("backend.agents.execution_agent.execute_sql")
@patch("backend.agents.validator_agent.get_known_tables")
@patch("backend.agents.workflow.retrieve_schema_context")
def test_workflow_runs_end_to_end_on_a_valid_question(mock_retrieve, mock_known_tables, mock_execute):
    mock_retrieve.return_value = FAKE_SCHEMA_CONTEXT
    mock_known_tables.return_value = {"orders": {"product", "total_price"}}
    mock_execute.return_value = (
        ["product", "total_price"],
        [{"product": "Laptop", "total_price": 12000.0}],
    )

    workflow = build_workflow(FakeLLMProvider())
    final_state = workflow.invoke(
        {"question": "Which product had the highest total sales?", "history": []}
    )

    assert final_state["is_valid"] is True
    assert "product" in final_state["sql"].lower()
    assert final_state["row_count"] == 1
    assert final_state["explanation"]
    assert final_state["execution_error"] is None
    assert final_state["chart_spec"]["type"] in ("bar", "line", "scatter", "kpi", "table")


@patch("backend.agents.execution_agent.execute_sql")
@patch("backend.agents.validator_agent.get_known_tables")
@patch("backend.agents.workflow.retrieve_schema_context")
def test_workflow_repairs_after_a_validation_failure(mock_retrieve, mock_known_tables, mock_execute):
    """Force the validator to reject the first pass (unknown table), and
    confirm the repair loop kicks in and the graph still terminates cleanly
    rather than looping forever."""
    mock_retrieve.return_value = FAKE_SCHEMA_CONTEXT
    # First call: table not recognized (forces a repair). Second call
    # onward: recognized, so the repaired SQL validates.
    mock_known_tables.side_effect = [
        {"customers": {"id"}},
        {"orders": {"product", "total_price"}},
        {"orders": {"product", "total_price"}},
    ]
    mock_execute.return_value = (["product", "total_price"], [{"product": "Laptop", "total_price": 1.0}])

    workflow = build_workflow(FakeLLMProvider())
    final_state = workflow.invoke({"question": "Which product had the highest total sales?", "history": []})

    assert final_state["repair_attempts"] >= 1
    assert final_state["explanation"]


@patch("backend.agents.execution_agent.execute_sql")
@patch("backend.agents.validator_agent.get_known_tables")
@patch("backend.agents.workflow.retrieve_schema_context")
def test_workflow_gives_up_gracefully_after_max_repair_attempts(mock_retrieve, mock_known_tables, mock_execute):
    """If validation never succeeds, the graph must still terminate (not
    loop forever) and produce a state the explanation/visualization nodes
    can handle without raising."""
    mock_retrieve.return_value = FAKE_SCHEMA_CONTEXT
    mock_known_tables.return_value = {"customers": {"id"}}  # never matches "orders"
    mock_execute.return_value = ([], [])

    workflow = build_workflow(FakeLLMProvider())
    final_state = workflow.invoke({"question": "Which product had the highest total sales?", "history": []})

    assert final_state["is_valid"] is False
    assert final_state["explanation"]  # still produces a user-facing message, doesn't crash
