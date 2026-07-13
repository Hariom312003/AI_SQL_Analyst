"""Tests for backend.agents.validator_agent.validate_sql -- read-only
enforcement, hallucinated table/column detection, and CTE/alias handling.
No database or network needed: known_tables is a plain dict standing in for
what schema_catalog.get_known_tables() would return from a live inspector.
"""
from __future__ import annotations

from backend.agents.validator_agent import validate_sql

KNOWN_TABLES = {
    "orders": {"order_id", "product", "category", "region", "customer_name", "total_price", "order_date"},
}


def test_valid_select_passes():
    sql = (
        "SELECT product, SUM(total_price) AS total_price FROM orders "
        "GROUP BY product ORDER BY total_price DESC LIMIT 5;"
    )
    assert validate_sql(sql, KNOWN_TABLES) == []


def test_drop_table_is_rejected():
    errors = validate_sql("DROP TABLE orders;", KNOWN_TABLES)
    assert errors
    assert "SELECT" in errors[0]


def test_delete_is_rejected():
    errors = validate_sql("DELETE FROM orders WHERE product = 'Laptop';", KNOWN_TABLES)
    assert errors


def test_update_is_rejected():
    errors = validate_sql("UPDATE orders SET total_price = 0;", KNOWN_TABLES)
    assert errors


def test_insert_is_rejected():
    errors = validate_sql("INSERT INTO orders (product) VALUES ('Laptop');", KNOWN_TABLES)
    assert errors


def test_truncate_is_rejected():
    errors = validate_sql("TRUNCATE TABLE orders;", KNOWN_TABLES)
    assert errors


def test_unknown_table_is_rejected():
    errors = validate_sql("SELECT * FROM customers;", KNOWN_TABLES)
    assert any("Unknown table" in e for e in errors)


def test_unknown_column_is_rejected():
    errors = validate_sql("SELECT nonexistent_column FROM orders;", KNOWN_TABLES)
    assert any("Unknown column" in e for e in errors)


def test_stacked_statements_are_rejected():
    """Classic SQL-injection-style stacked query."""
    errors = validate_sql("SELECT * FROM orders; DROP TABLE orders;", KNOWN_TABLES)
    assert errors


def test_order_by_alias_is_not_flagged_as_unknown_column():
    """Regression test: Postgres allows ORDER BY/GROUP BY to reference a
    SELECT-list alias, even when that alias name doesn't match any real
    column. Before this fix, a differently-named alias (unlike our own
    heuristic generator's habit of reusing the column name as the alias)
    would have been incorrectly flagged as a hallucinated column."""
    sql = (
        "SELECT product, SUM(total_price) AS revenue FROM orders "
        "GROUP BY product ORDER BY revenue DESC;"
    )
    assert validate_sql(sql, KNOWN_TABLES) == []


def test_cte_self_reference_is_not_flagged_as_unknown_table():
    sql = (
        "WITH recent AS (SELECT * FROM orders WHERE order_date > '2025-01-01') "
        "SELECT product FROM recent;"
    )
    errors = validate_sql(sql, KNOWN_TABLES)
    assert not any("Unknown table" in e for e in errors)


def test_unparseable_sql_is_rejected_gracefully():
    errors = validate_sql("SELECT FROM WHERE;;;", KNOWN_TABLES)
    assert errors  # should fail cleanly, not raise
