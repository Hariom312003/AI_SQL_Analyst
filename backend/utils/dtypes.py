"""Shared pandas dtype-checking helpers.

pandas>=2.1 can report text columns as the newer StringDtype (dtype 'str')
instead of the legacy 'object' dtype, depending on the future.infer_string
option -- which pandas 3.0 enables by default (confirmed empirically: this
project's pandas 3.0.2 reports text columns as 'str'). Checking
`dtype == object` alone silently misses these columns. Centralized here
since both backend/database/ingestion.py and backend/agents/dashboard_agent.py
need the same "is this a text column" check -- fixing it in one place only
is exactly how the dashboard chart generation broke silently.
"""
from __future__ import annotations

import pandas as pd


def is_text_like(series: pd.Series) -> bool:
    """True for both the legacy object dtype and the newer StringDtype."""
    return series.dtype == object or pd.api.types.is_string_dtype(series)


def is_identifier_like(column_name: str) -> bool:
    """Heuristic: does this column name look like a row identifier rather
    than a meaningful metric? Deliberately exact/suffix matching only
    ('id', '*_id') rather than a substring check -- a substring check would
    misfire on ordinary words like 'paid' or 'void' that happen to contain
    'id'."""
    name = column_name.lower()
    return name == "id" or name.endswith("_id")
