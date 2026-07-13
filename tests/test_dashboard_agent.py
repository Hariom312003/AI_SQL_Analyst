"""Tests for backend.agents.dashboard_agent.build_dashboard_spec.

test_dashboard_includes_a_chart_when_categorical_and_numeric_columns_exist
is a direct regression test for a real bug found during live end-to-end
testing: `df[c].dtype == object` silently matched zero columns under
pandas>=2.1's StringDtype default, so no chart was ever generated even
though the fix in ingestion.py's schema inference didn't touch this file.
"""
from __future__ import annotations

import pandas as pd

from backend.agents.dashboard_agent import build_dashboard_spec


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "order_id": range(1, 11),
            "product": ["Laptop", "Mouse"] * 5,
            "total_price": [100.0, 20.0] * 5,
        }
    )


def test_dashboard_includes_row_count_card():
    spec = build_dashboard_spec("orders", _sample_df())
    assert {"label": "Row count", "value": 10} in spec["kpi_cards"]


def test_dashboard_excludes_identifier_columns_from_kpi_totals():
    spec = build_dashboard_spec("orders", _sample_df())
    labels = [c["label"] for c in spec["kpi_cards"]]
    assert "Total order_id" not in labels


def test_dashboard_includes_a_real_metric_kpi():
    spec = build_dashboard_spec("orders", _sample_df())
    labels = {c["label"]: c["value"] for c in spec["kpi_cards"]}
    assert labels["Total total_price"] == 600.0


def test_dashboard_includes_a_chart_when_categorical_and_numeric_columns_exist():
    spec = build_dashboard_spec("orders", _sample_df())
    assert len(spec["charts"]) == 1
    chart = spec["charts"][0]
    assert chart["type"] in ("bar", "line", "scatter")
    assert chart["data"]


def test_dashboard_handles_no_categorical_columns_gracefully():
    df = pd.DataFrame({"order_id": range(1, 6), "total_price": [1.0, 2.0, 3.0, 4.0, 5.0]})
    spec = build_dashboard_spec("orders", df)
    assert spec["charts"] == []
