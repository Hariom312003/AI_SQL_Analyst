"""Tests for backend.database.ingestion -- header cleaning and schema
inference. Deliberately does not touch a real Postgres table (ingest_csv
itself needs a live engine); those two functions are pure pandas logic and
fully testable in isolation.
"""
from __future__ import annotations

import pandas as pd

from backend.database.ingestion import _auto_describe, clean_headers, infer_schema


def test_clean_headers_normalizes_case_and_spacing():
    assert clean_headers(["Order ID", "Total Price"]) == ["order_id", "total_price"]


def test_clean_headers_strips_special_characters():
    assert clean_headers(["Revenue (USD)!!", "% Growth"]) == ["revenue_usd", "growth"]


def test_clean_headers_dedupes_collisions():
    cleaned = clean_headers(["Total Price", "total_price", "  "])
    assert cleaned[0] == "total_price"
    assert cleaned[1] == "total_price_1"
    assert cleaned[2] == "field"


def test_infer_schema_detects_datetime_column():
    df = pd.DataFrame({"order_date": ["2025-01-15", "2025-02-20", "2025-06-03"]})
    dtypes = infer_schema(df)
    assert dtypes["order_date"].startswith("datetime64")


def test_infer_schema_coerces_numeric_strings():
    df = pd.DataFrame({"quantity": ["1", "2", "3", "4"]})
    dtypes = infer_schema(df)
    assert dtypes["quantity"] in ("int64", "float64")


def test_infer_schema_leaves_genuine_text_alone():
    df = pd.DataFrame({"product": ["Laptop", "Mouse", "Keyboard", "Monitor"]})
    dtypes = infer_schema(df)
    assert dtypes["product"] == "object"


def test_infer_schema_does_not_misdetect_short_text_as_dates():
    df = pd.DataFrame({"category": ["Electronics", "Furniture", "Office Supplies"]})
    dtypes = infer_schema(df)
    assert dtypes["category"] == "object"


def test_auto_describe_flags_monetary_columns():
    assert "monetary" in _auto_describe("total_price", "float64", []).lower()


def test_auto_describe_flags_identifier_columns():
    assert "identifier" in _auto_describe("order_id", "int64", []).lower()


def test_auto_describe_flags_datetime_columns():
    assert "date" in _auto_describe("order_date", "datetime64[ns]", []).lower()


def test_auto_describe_includes_samples_for_categorical_columns():
    desc = _auto_describe("product", "object", ["Laptop", "Mouse", "Keyboard"])
    assert "Laptop" in desc
