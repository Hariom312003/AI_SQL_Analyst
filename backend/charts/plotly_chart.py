"""Turns a Visualization Agent chart_spec (heuristic: what type of chart, what
data) into an actual rendered Plotly figure. Kept as its own module so the
API can return ready-to-render figure JSON -- any client (Streamlit today,
potentially a future React frontend using react-plotly.js) just plots it
directly, with zero chart-building logic of its own."""
from __future__ import annotations

import json

import plotly.graph_objects as go
import plotly.io as pio

_BUILDERS = {
    "line": lambda xs, ys: go.Scatter(x=xs, y=ys, mode="lines+markers"),
    "bar": lambda xs, ys: go.Bar(x=xs, y=ys),
    "scatter": lambda xs, ys: go.Scatter(x=xs, y=ys, mode="markers"),
}


def build_figure(chart_spec: dict) -> go.Figure | None:
    chart_type = chart_spec.get("type")
    data = chart_spec.get("data")
    if not data or chart_type in (None, "table", "kpi"):
        return None

    x_key, y_key = chart_spec["x"], chart_spec["y"]
    xs = [row.get(x_key) for row in data]
    ys = [row.get(y_key) for row in data]

    trace_builder = _BUILDERS.get(chart_type, _BUILDERS["bar"])
    fig = go.Figure(trace_builder(xs, ys))
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=380, xaxis_title=x_key, yaxis_title=y_key)
    return fig


def figure_to_dict(fig: go.Figure) -> dict:
    """Plotly figures can contain numpy scalars that FastAPI's default JSON
    encoder chokes on -- round-tripping through plotly's own JSON encoder
    guarantees a plain, JSON-safe dict."""
    return json.loads(pio.to_json(fig))
