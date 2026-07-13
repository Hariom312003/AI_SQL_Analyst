"""Reflects the *actual* live Postgres schema (not just our own metadata
records) so the SQL Validator Agent can catch hallucinated tables/columns
against ground truth."""
from __future__ import annotations

from sqlalchemy import inspect

from backend.database.postgres import sync_engine


def get_known_tables() -> dict[str, set[str]]:
    inspector = inspect(sync_engine)
    known: dict[str, set[str]] = {}
    for table_name in inspector.get_table_names():
        columns = {col["name"].lower() for col in inspector.get_columns(table_name)}
        known[table_name.lower()] = columns
    return known
