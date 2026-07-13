"""Deterministic, offline, rule-based LLM stand-in.

This exists so the whole agent pipeline (intent -> schema retrieval -> SQL
generation -> validation -> repair -> execution -> explanation) runs
end-to-end with zero external API calls or credentials -- useful for local
development, automated tests, and demos. It is intentionally simple and will
NOT understand truly open-ended natural language the way a real LLM does.
Set LLM_PROVIDER=anthropic (with ANTHROPIC_API_KEY) for real NLU quality.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from backend.llm.base import LLMProvider

_NUMERIC_TYPES = {"BigInteger", "Float", "Integer"}

_SUM_WORDS = {"total", "sum", "revenue", "sale"}
_AVG_WORDS = {"average", "avg", "mean"}
_COUNT_WORDS = {"count", "many"}
_DESC_WORDS = {"highest", "most", "maximum", "max", "top", "largest", "greatest"}
_ASC_WORDS = {"lowest", "least", "minimum", "min", "smallest", "worst"}
_FRAGMENT_MARKERS = {"show", "which", "what", "how", "list", "compare"}

_STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "of", "in", "on", "for", "to",
    "and", "or", "what", "which", "how", "many", "show", "me", "please", "this",
    "that", "i", "e", "with", "by", "did", "do", "does", "has", "have", "had",
}

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _normalize(tok: str) -> str:
    if len(tok) > 4 and tok.endswith("ies"):
        return tok[:-3] + "y"
    if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
        return tok[:-1]
    return tok


def _tokens(text: str) -> set[str]:
    return {_normalize(t) for t in re.findall(r"[a-z0-9]+", text.lower())}


def _content_tokens(text: str) -> set[str]:
    return _tokens(text) - _STOPWORDS


def _columns_from_context(schema_context: list[dict]) -> list[dict]:
    return [c for c in schema_context if c["metadata"].get("type") == "column"]


def _table_from_context(schema_context: list[dict]) -> str:
    for item in schema_context:
        table_name = item["metadata"].get("table_name")
        if table_name:
            return table_name
    return "unknown_table"


def _score(q_tokens: set[str], col: dict) -> float:
    name = col["metadata"].get("column_name", "")
    name_tokens = _content_tokens(name.replace("_", " ") + " " + col.get("text", ""))
    overlap = len(q_tokens & name_tokens)
    ratio = SequenceMatcher(None, " ".join(sorted(q_tokens)), name).ratio()
    return overlap * 2 + ratio


def _best_column(q_tokens: set[str], columns: list[dict]) -> dict | None:
    scored = [(_score(q_tokens, c), c) for c in columns]
    scored = [(s, c) for s, c in scored if s >= 2]  # require >=1 real overlapping word
    if not scored:
        return None
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[0][1]


def _detect_aggregation(q_tokens: set[str]) -> str | None:
    if q_tokens & _SUM_WORDS:
        return "SUM"
    if q_tokens & _AVG_WORDS:
        return "AVG"
    if q_tokens & _COUNT_WORDS:
        return "COUNT"
    if q_tokens & (_DESC_WORDS | _ASC_WORDS):
        return "SUM"
    return None


def _detect_categorical_filter(question: str, categorical_columns: list[dict]) -> tuple[str, str] | None:
    q_lower = question.lower()
    for col in categorical_columns:
        for val in col["metadata"].get("sample_values") or []:
            if str(val).lower() in q_lower:
                return col["metadata"]["column_name"], str(val)
    return None


def _build_sql(question: str, schema_context: list[dict]) -> str:
    content_tokens = _content_tokens(question)
    raw_tokens = _tokens(question)
    table = _table_from_context(schema_context)
    columns = _columns_from_context(schema_context)
    numeric_columns = [c for c in columns if c["metadata"].get("sql_type") in _NUMERIC_TYPES]
    categorical_columns = [c for c in columns if c["metadata"].get("sql_type") == "Text"]
    date_columns = [c for c in columns if c["metadata"].get("sql_type") == "DateTime"]

    agg = _detect_aggregation(raw_tokens)
    direction = "DESC" if raw_tokens & _DESC_WORDS else "ASC" if raw_tokens & _ASC_WORDS else None
    limit_match = re.search(r"top\s+(\d+)", question.lower())
    limit = int(limit_match.group(1)) if limit_match else (1 if direction else None)

    metric_col = _best_column(content_tokens, numeric_columns)
    if metric_col is None and agg and numeric_columns:
        metric_col = numeric_columns[0]

    # A specific VALUE from a categorical column (e.g. "Electronics") signals a
    # filter, not a group-by choice -- so exclude that column from dimension
    # candidacy before picking the dimension (see README for the "Only
    # Electronics" follow-up example this resolves correctly).
    cat_filter = _detect_categorical_filter(question, categorical_columns)
    dimension_candidates = categorical_columns
    if cat_filter:
        dimension_candidates = [c for c in categorical_columns if c["metadata"]["column_name"] != cat_filter[0]]
    dimension_col = _best_column(content_tokens, dimension_candidates)

    metric_name = metric_col["metadata"]["column_name"] if metric_col else None
    dimension_name = dimension_col["metadata"]["column_name"] if dimension_col else None

    where_clauses = []
    month_hit = next((m for m in _MONTHS if m in question.lower()), None)
    if month_hit and date_columns:
        date_col_name = date_columns[0]["metadata"]["column_name"]
        where_clauses.append(f"EXTRACT(MONTH FROM {date_col_name}) = {_MONTHS[month_hit]}")
    if cat_filter:
        col_name, value = cat_filter
        where_clauses.append(f"{col_name} = '{value.replace(chr(39), chr(39) * 2)}'")

    if agg == "COUNT":
        select_expr, alias = "COUNT(*)", "count"
    elif agg and metric_name:
        select_expr, alias = f"{agg}({metric_name})", metric_name
    elif metric_name:
        select_expr, alias = metric_name, metric_name
    else:
        select_expr, alias = "*", None

    if dimension_name and alias:
        select_clause = f"{dimension_name}, {select_expr} AS {alias}"
        group_clause = f"GROUP BY {dimension_name}"
        order_clause = f"ORDER BY {alias} {direction or 'DESC'}"
    elif alias:
        select_clause, group_clause, order_clause = f"{select_expr} AS {alias}", "", ""
    else:
        select_clause, group_clause, order_clause = select_expr, "", ""

    parts = [f"SELECT {select_clause}", f"FROM {table}"]
    if where_clauses:
        parts.append("WHERE " + " AND ".join(where_clauses))
    if group_clause:
        parts.append(group_clause)
    if order_clause:
        parts.append(order_clause)
    if limit:
        parts.append(f"LIMIT {limit}")

    return "\n".join(parts) + ";"


class FakeLLMProvider(LLMProvider):
    """Heuristic NL->SQL / summarization used when no real LLM is configured."""

    def resolve_intent(self, question: str, history: list[dict]) -> dict:
        raw_tokens = _tokens(question)
        prior_user = next((h["content"] for h in reversed(history) if h["role"] == "user"), None)
        looks_like_fragment = len(question.split()) <= 6 and not (raw_tokens & _FRAGMENT_MARKERS)
        resolved = f"{prior_user} ({question})" if (prior_user and looks_like_fragment) else question

        if raw_tokens & (_DESC_WORDS | _ASC_WORDS):
            intent_type = "ranking"
        elif raw_tokens & (_SUM_WORDS | _AVG_WORDS | _COUNT_WORDS):
            intent_type = "aggregation"
        elif "compare" in raw_tokens or "vs" in raw_tokens:
            intent_type = "comparison"
        elif "trend" in raw_tokens:
            intent_type = "trend"
        else:
            intent_type = "lookup"

        return {"resolved_question": resolved, "intent_type": intent_type, "filters": []}

    def generate_sql(self, question: str, schema_context: list[dict]) -> str:
        return _build_sql(question, schema_context)

    def repair_sql(self, question: str, schema_context: list[dict], bad_sql: str, error: str) -> str:
        # A real LLM would reason about the specific error message; this
        # fallback just regenerates from scratch against the schema context.
        return _build_sql(question, schema_context)

    def explain_results(self, question: str, sql: str, columns: list[str], rows: list[dict]) -> str:
        if not rows:
            return "The query ran successfully but returned no matching rows."

        if len(columns) == 1:
            label = columns[0].replace("_", " ").title()
            value = rows[0].get(columns[0])
            formatted = f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)
            return f"{label}: {formatted}."

        label_col, metric_col = columns[0], columns[-1]
        if isinstance(rows[0].get(metric_col), (int, float)):
            top = rows[0]
            if len(rows) == 1:
                return f"'{top[label_col]}' leads with {top[metric_col]:,.2f} for {metric_col}."
            total = sum(r[metric_col] for r in rows if isinstance(r.get(metric_col), (int, float)))
            share = (top[metric_col] / total * 100) if total else 0
            return (
                f"'{top[label_col]}' leads with {top[metric_col]:,.2f} for {metric_col}, "
                f"{share:.0f}% of the total across the {len(rows)} row(s) shown."
            )
        return f"The query returned {len(rows)} row(s) across {len(columns)} column(s)."
