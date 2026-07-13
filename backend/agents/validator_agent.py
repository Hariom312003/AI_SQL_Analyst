"""Validator Agent -- syntax check, read-only enforcement, and hallucinated
table/column detection using sqlglot against the live Postgres schema."""
from __future__ import annotations

import sqlglot
from sqlglot import exp

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.database.schema_catalog import get_known_tables


def validate_sql(sql: str, known_tables: dict[str, set[str]]) -> list[str]:
    sql_clean = sql.strip().rstrip(";")

    try:
        statements = sqlglot.parse(sql_clean, read="postgres")
    except Exception as exc:  # noqa: BLE001
        return [f"SQL failed to parse: {exc}"]

    if len(statements) != 1 or statements[0] is None:
        return ["Only a single SQL statement is allowed."]

    tree = statements[0]

    # A single top-level statement that isn't a SELECT can only be DDL/DML
    # (DROP/DELETE/UPDATE/ALTER/TRUNCATE/INSERT/...) -- SQL grammar doesn't
    # allow those to appear nested inside a SELECT, so this one check is a
    # complete, sqlglot-version-independent read-only guarantee.
    if not isinstance(tree, exp.Select):
        return ["Only SELECT statements are permitted (read-only enforcement)."]

    errors: list[str] = []
    cte_names = {cte.alias.lower() for cte in tree.find_all(exp.CTE) if cte.alias}
    referenced_tables = {t.name.lower() for t in tree.find_all(exp.Table)} - cte_names
    unknown_tables = referenced_tables - set(known_tables)
    if unknown_tables:
        errors.append(f"Unknown table(s) referenced: {', '.join(sorted(unknown_tables))}.")

    # Best-effort column-level check, skipped for CTEs (a CTE can introduce
    # computed/renamed columns that won't match the physical schema).
    if not unknown_tables and not cte_names:
        aliases = {sel.alias.lower() for sel in tree.selects if getattr(sel, "alias", None)}
        all_known_columns = {col for cols in known_tables.values() for col in cols}
        for col_expr in tree.find_all(exp.Column):
            col_name = col_expr.name.lower()
            if col_name in ("", "*") or col_name in aliases:
                continue
            if col_name not in all_known_columns:
                errors.append(f"Unknown column referenced: '{col_name}'.")

    return errors


@instrumented("validator_agent")
def run(state: AgentState) -> AgentState:
    known_tables = get_known_tables()
    errors = validate_sql(state["sql"], known_tables)
    state["is_valid"] = not errors
    state["validation_errors"] = errors
    return state
