"""Dashboard Agent -- assembles a lightweight dashboard spec (KPI cards +
charts) for a dataset. This is the data-assembly half of module 8 (Dashboard
Generator); Streamlit (app.py) renders it, so filters/drill-down/downloads
live in the UI layer, not here."""
from __future__ import annotations

import pandas as pd

from backend.agents.instrumentation import instrumented
from backend.agents.visualization_agent import choose_chart
from backend.utils.dtypes import is_identifier_like, is_text_like


@instrumented("dashboard_agent")
def build_dashboard_spec(table_name: str, df: pd.DataFrame) -> dict:
    numeric_cols = [c for c in df.select_dtypes(include="number").columns if not is_identifier_like(c)]
    categorical_cols = [c for c in df.columns if is_text_like(df[c])]

    kpi_cards = [{"label": "Row count", "value": len(df)}]
    for col in numeric_cols[:3]:
        kpi_cards.append({"label": f"Total {col}", "value": float(df[col].sum())})

    charts = []
    if categorical_cols and numeric_cols:
        dim, metric = categorical_cols[0], numeric_cols[0]
        grouped = (
            df.groupby(dim)[metric].sum().reset_index().sort_values(metric, ascending=False).head(10)
        )
        charts.append(choose_chart([dim, metric], grouped.to_dict("records")))

    return {"table_name": table_name, "kpi_cards": kpi_cards, "charts": charts}
