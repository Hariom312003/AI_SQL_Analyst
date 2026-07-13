"""Execution Agent -- safely runs a validated, read-only statement against
Postgres with a hard row cap and a statement timeout."""
from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from backend.agents.instrumentation import instrumented
from backend.agents.state import AgentState
from backend.config import get_settings

settings = get_settings()


class SQLExecutionError(Exception):
    pass


def execute_sql(sql: str, engine: Engine) -> tuple[list[str], list[dict]]:
    sql_clean = sql.strip().rstrip(";")
    limited_sql = f"SELECT * FROM ({sql_clean}) AS _subquery LIMIT {settings.max_result_rows}"
    try:
        with engine.connect() as conn:
            conn.execute(text("SET statement_timeout = '5s'"))
            result = conn.execute(text(limited_sql))
            columns = list(result.keys())
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
        return columns, rows
    except Exception as exc:  # noqa: BLE001
        raise SQLExecutionError(str(exc)) from exc


@instrumented("execution_agent")
def run(state: AgentState, engine: Engine) -> AgentState:
    try:
        columns, rows = execute_sql(state["sql"], engine)
        state["result_columns"] = columns
        state["result_rows"] = rows
        state["row_count"] = len(rows)
        state["execution_error"] = None
    except SQLExecutionError as exc:
        state["execution_error"] = str(exc)
    return state
