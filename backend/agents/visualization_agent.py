"""Visualization Agent -- heuristically chooses a chart type + spec based on
the shape of the result set (module 7: Chart Generator). Actual Plotly
figure rendering lives in backend/charts/plotly_chart.py -- kept separate so
this agent stays a pure, easily-testable function of (columns, rows) -> spec."""
from __future__ import annotations

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState


def choose_chart(columns: list[str], rows: list[dict]) -> dict:
    if not rows or not columns:
        return {"type": "table", "reason": "No data to visualize."}

    if len(columns) == 1:
        return {"type": "kpi", "columns": columns, "reason": "Single-value result."}

    dimension, metric = columns[0], columns[-1]
    sample_metric = next((r[metric] for r in rows if r.get(metric) is not None), None)

    if not isinstance(sample_metric, (int, float)):
        return {"type": "table", "columns": columns, "reason": "No numeric metric detected."}

    looks_like_time = any(key in dimension.lower() for key in ("date", "month", "year", "time", "day"))
    if looks_like_time:
        chart_type = "line"
    elif len(columns) == 2:
        chart_type = "bar"
    else:
        chart_type = "scatter"

    return {
        "type": chart_type,
        "x": dimension,
        "y": metric,
        "data": [{dimension: r.get(dimension), metric: r.get(metric)} for r in rows],
    }


@instrumented("visualization_agent")
def run(state: AgentState) -> AgentState:
    state["chart_spec"] = choose_chart(state.get("result_columns", []), state.get("result_rows", []))
    return state
