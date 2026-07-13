"""Loads dataset/table/column metadata from the database and turns it into
retrieval documents for the RAG layer (module: schema-aware RAG knowledge
base -- table descriptions, column descriptions, business glossary, sample
values all get embedded here)."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.database.models import Dataset
from backend.database.postgres import sync_engine


@dataclass
class SchemaDocument:
    id: str
    text: str
    metadata: dict = field(default_factory=dict)


def load_schema_documents() -> list[SchemaDocument]:
    docs: list[SchemaDocument] = []
    with Session(sync_engine) as session:
        datasets = session.scalars(select(Dataset)).all()
        for ds in datasets:
            docs.append(
                SchemaDocument(
                    id=f"table:{ds.table_name}",
                    text=(
                        f"Table '{ds.table_name}' (dataset: {ds.name}). "
                        f"{ds.description or 'No description provided.'} Contains {ds.row_count} rows."
                    ),
                    metadata={"type": "table", "table_name": ds.table_name, "dataset_id": str(ds.id)},
                )
            )
            for col in ds.columns:
                samples = ", ".join(str(v) for v in (col.sample_values or [])[:3])
                docs.append(
                    SchemaDocument(
                        id=f"column:{ds.table_name}.{col.column_name}",
                        text=(
                            f"Column '{col.column_name}' in table '{ds.table_name}'. "
                            f"Type: {col.sql_type}. {col.description or ''} Example values: {samples}."
                        ),
                        metadata={
                            "type": "column",
                            "table_name": ds.table_name,
                            "column_name": col.column_name,
                            "sql_type": col.sql_type,
                            "sample_values": col.sample_values or [],
                            "dataset_id": str(ds.id),
                        },
                    )
                )
    return docs
