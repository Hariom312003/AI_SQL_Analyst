"""Prompt templates for the SQL Generation and SQL Repair agents."""
from __future__ import annotations

SQL_GENERATION_SYSTEM_PROMPT = (
    "You are the SQL Generation Agent of an enterprise analytics platform. "
    "Write exactly one PostgreSQL SELECT statement that answers the question, "
    "using ONLY the tables/columns given in the schema context. Never write DDL/DML. "
    'Respond as JSON: {"sql": str}'
)

SQL_REPAIR_SYSTEM_PROMPT = (
    "You are the SQL Repair Agent. The previous SQL failed validation or execution. "
    "Read the error, consult the schema context, and produce a corrected single "
    'PostgreSQL SELECT statement. Respond as JSON: {"sql": str}'
)


def format_schema_context(schema_context: list[dict]) -> str:
    return "\n".join(f"- {item['text']}" for item in schema_context)


def build_sql_generation_user_prompt(question: str, schema_context: list[dict]) -> str:
    return f"Schema context:\n{format_schema_context(schema_context)}\n\nQuestion: {question}"


def build_sql_repair_user_prompt(
    question: str, schema_context: list[dict], bad_sql: str, error: str
) -> str:
    return (
        f"Schema context:\n{format_schema_context(schema_context)}\n\nQuestion: {question}\n\n"
        f"Previous SQL:\n{bad_sql}\n\nError:\n{error}"
    )
