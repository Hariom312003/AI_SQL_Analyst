"""Tests for backend.llm.fake_provider.FakeLLMProvider -- the deterministic
offline NL->SQL fallback. These pin down the exact heuristic behaviors this
project's demo relies on: metric/dimension detection by column type,
month filters, top-N limits, and the categorical-filter-vs-dimension
priority rule that makes conversational follow-ups like 'Only Electronics'
resolve correctly.
"""
from __future__ import annotations

from backend.llm.fake_provider import FakeLLMProvider

ORDERS_SCHEMA = [
    {"text": "Table 'orders'.", "metadata": {"type": "table", "table_name": "orders"}},
    {
        "text": "Column 'product' in table 'orders'. Name of the product sold. Example values: Laptop, Mouse, Keyboard.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "product",
            "sql_type": "Text", "sample_values": ["Laptop", "Mouse", "Keyboard"],
        },
    },
    {
        "text": "Column 'category' in table 'orders'. Broad classification. Example values: Electronics, Furniture.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "category",
            "sql_type": "Text", "sample_values": ["Electronics", "Furniture"],
        },
    },
    {
        "text": "Column 'customer_name' in table 'orders'. Name of the customer. Example values: Customer 1, Customer 2.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "customer_name",
            "sql_type": "Text", "sample_values": ["Customer 1", "Customer 2"],
        },
    },
    {
        "text": "Column 'total_price' in table 'orders'. Final price after discount, the sale revenue for the order line.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "total_price",
            "sql_type": "Float", "sample_values": [],
        },
    },
    {
        "text": "Column 'order_date' in table 'orders'. Date the order was placed.",
        "metadata": {
            "type": "column", "table_name": "orders", "column_name": "order_date",
            "sql_type": "DateTime", "sample_values": [],
        },
    },
]

provider = FakeLLMProvider()


def test_simple_total_has_no_spurious_group_by():
    sql = provider.generate_sql("What is the total revenue?", ORDERS_SCHEMA)
    assert "SUM(total_price)" in sql
    assert "GROUP BY" not in sql.upper()


def test_ranking_question_groups_orders_and_limits_to_one():
    sql = provider.generate_sql("Which product had the highest total sales in June?", ORDERS_SCHEMA)
    assert "product" in sql
    assert "SUM(total_price)" in sql
    assert "EXTRACT(MONTH FROM order_date) = 6" in sql
    assert "ORDER BY total_price DESC" in sql
    assert "LIMIT 1" in sql


def test_top_n_pattern_sets_explicit_limit():
    sql = provider.generate_sql("Show top 5 customers by revenue", ORDERS_SCHEMA)
    assert "customer_name" in sql
    assert "LIMIT 5" in sql
    assert "ORDER BY total_price DESC" in sql


def test_categorical_value_mention_becomes_a_filter_not_a_dimension():
    """The tricky case: a follow-up like 'Only Electronics' names a VALUE of
    the category column, not the category column itself -- it should become
    a WHERE filter while the original group-by-product intent is preserved,
    not get treated as if the user wanted to group by category."""
    sql = provider.generate_sql(
        "Show total sales by product (Only Electronics)", ORDERS_SCHEMA
    )
    assert "category = 'Electronics'" in sql
    assert "GROUP BY product" in sql
    assert "GROUP BY category" not in sql


def test_resolve_intent_folds_short_followup_onto_prior_question():
    history = [
        {"role": "user", "content": "Show total sales by product"},
        {"role": "assistant", "content": "Here you go."},
    ]
    result = provider.resolve_intent("Only Electronics", history)
    assert "Show total sales by product" in result["resolved_question"]
    assert "Only Electronics" in result["resolved_question"]


def test_resolve_intent_leaves_a_full_new_question_alone():
    result = provider.resolve_intent("Which product had the highest total sales?", [])
    assert result["resolved_question"] == "Which product had the highest total sales?"
    assert result["intent_type"] == "ranking"


def test_explain_results_handles_empty_rows():
    explanation = provider.explain_results("any question", "SELECT 1;", ["x"], [])
    assert "no matching rows" in explanation.lower()


def test_explain_results_gives_a_real_answer_for_a_single_value():
    """Regression test: a single-column aggregate result (e.g. 'total
    revenue') used to fall through to a generic 'returned 1 row across 1
    column' non-answer instead of stating the value."""
    explanation = provider.explain_results(
        "What is the total revenue?", "SELECT SUM(total_price) AS total_price FROM orders;",
        ["total_price"], [{"total_price": 123456.78}],
    )
    assert "123,456.78" in explanation
    assert "row" not in explanation.lower()


def test_explain_results_avoids_tautological_percentage_for_a_single_row():
    """Regression test: a single-row ranking result (e.g. 'highest product')
    used to say '100% of the total across the 1 row shown', which is always
    true and therefore meaningless."""
    explanation = provider.explain_results(
        "Which product had the highest sales?", "SELECT ...",
        ["product", "total_price"], [{"product": "Laptop", "total_price": 5000.0}],
    )
    assert "Laptop" in explanation
    assert "100%" not in explanation


def test_explain_results_leads_with_the_top_row():
    rows = [
        {"product": "Laptop", "total_price": 9500.0},
        {"product": "Mouse", "total_price": 500.0},
    ]
    explanation = provider.explain_results("q", "SELECT ...", ["product", "total_price"], rows)
    assert "Laptop" in explanation
    assert "9,500" in explanation or "9500" in explanation
