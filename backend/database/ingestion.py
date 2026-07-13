"""CSV ingestion pipeline (module 1: CSV Upload).

Covers: encoding detection -> schema inference -> header cleaning -> Postgres
table creation -> data insertion -> metadata capture. RAG indexing and
profiling are triggered by the caller (routes.py) after this returns, since
they're separate concerns (module boundaries matter for testability).
"""
from __future__ import annotations

import io
import uuid
import warnings
from dataclasses import dataclass

import pandas as pd
from charset_normalizer import from_bytes
from sqlalchemy import BigInteger, Boolean, DateTime, Float, Text
from sqlalchemy.engine import Engine

from backend.utils.dtypes import is_identifier_like, is_text_like
from backend.utils.text import slugify

_SQLALCHEMY_TYPE_MAP = {
    "int64": BigInteger,
    "float64": Float,
    "bool": Boolean,
    "datetime64[ns]": DateTime,
    "object": Text,
}

_MONEY_HINTS = ("price", "amount", "revenue", "total", "cost", "sale", "sales")


def clean_headers(columns: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: dict[str, int] = {}
    for col in columns:
        slug = slugify(str(col))
        if slug in seen:
            seen[slug] += 1
            slug = f"{slug}_{seen[slug]}"
        else:
            seen[slug] = 0
        cleaned.append(slug)
    return cleaned


def detect_encoding(raw: bytes) -> str:
    match = from_bytes(raw).best()
    return match.encoding if match else "utf-8"


def _try_parse_datetime(series: pd.Series) -> pd.Series | None:
    if not is_text_like(series):
        return None
    sample = series.dropna().head(25)
    if sample.empty:
        return None
    try:
        with warnings.catch_warnings():
            # Mixed/ambiguous formats make pandas warn that it's falling back
            # to per-element dateutil parsing. We already handle both
            # outcomes (parses well -> use it, doesn't -> treat as text), so
            # the warning would just be noise on every non-date text column.
            warnings.simplefilter("ignore", UserWarning)
            parsed = pd.to_datetime(sample, errors="raise")
    except (ValueError, TypeError):
        return None
    if parsed.notna().mean() < 0.9:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        return pd.to_datetime(series, errors="coerce")


def infer_schema(df: pd.DataFrame) -> dict[str, str]:
    """Mutates df in place (type coercion) and returns {column: pandas_dtype_string}.

    Normalizes the "genuinely text" case to the label "object" even when the
    installed pandas reports the newer StringDtype ('str') instead -- keeps
    one consistent dtype vocabulary for _SQLALCHEMY_TYPE_MAP and everything
    downstream (RAG descriptions, the fake-provider heuristic, tests)
    regardless of which pandas version this runs on.
    """
    inferred = {}
    for col in df.columns:
        parsed_dates = _try_parse_datetime(df[col])
        if parsed_dates is not None:
            df[col] = parsed_dates
            inferred[col] = "datetime64[ns]"
            continue

        if is_text_like(df[col]):
            coerced = pd.to_numeric(df[col], errors="coerce")
            if coerced.notna().mean() >= 0.95 and df[col].notna().any():
                df[col] = coerced
                inferred[col] = str(df[col].dtype)
            else:
                inferred[col] = "object"
        else:
            inferred[col] = str(df[col].dtype)
    return inferred


def _auto_describe(column_name: str, dtype: str, samples: list[str]) -> str:
    """Generates a basic starter data-dictionary entry. Meant to be *overridden*
    via the column-description API once a human enriches the business glossary
    (see routes.py PATCH /datasets/{id}/columns/{name}) -- that's what actually
    powers high-quality RAG retrieval, this is just a reasonable default."""
    name = column_name.lower()
    if dtype.startswith("datetime"):
        return "Date/time field."
    if any(k in name for k in _MONEY_HINTS):
        return "Numeric monetary field."
    if is_identifier_like(column_name):
        return "Identifier field."
    if dtype in ("int64", "float64"):
        return "Numeric measure."
    sample_text = ", ".join(samples[:3])
    return f"Categorical/text field. Example values: {sample_text}."


@dataclass
class IngestionResult:
    table_name: str
    row_count: int
    columns: list[dict]


def ingest_csv(file_bytes: bytes, dataset_name: str, sync_engine: Engine) -> IngestionResult:
    encoding = detect_encoding(file_bytes[:20000])
    df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding)
    df.columns = clean_headers(list(df.columns))

    dtypes = infer_schema(df)
    table_name = f"ds_{slugify(dataset_name)}_{uuid.uuid4().hex[:6]}"
    sql_dtypes = {col: _SQLALCHEMY_TYPE_MAP.get(dtype, Text) for col, dtype in dtypes.items()}

    df.to_sql(
        table_name,
        con=sync_engine,
        if_exists="replace",
        index=False,
        dtype=sql_dtypes,
        chunksize=5000,
        method="multi",
    )

    columns_meta = []
    for col in df.columns:
        samples = df[col].dropna().astype(str).unique()[:5].tolist()
        columns_meta.append(
            {
                "column_name": col,
                "inferred_dtype": dtypes[col],
                "sql_type": sql_dtypes[col].__name__,
                "sample_values": samples,
                "description": _auto_describe(col, dtypes[col], samples),
            }
        )

    return IngestionResult(table_name=table_name, row_count=len(df), columns=columns_meta)
