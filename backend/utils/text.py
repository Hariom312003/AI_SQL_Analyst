"""Small text utilities shared across the ingestion pipeline."""
from __future__ import annotations

import re


def slugify(name: str) -> str:
    """Turn an arbitrary header/name into a safe snake_case SQL identifier fragment."""
    name = re.sub(r"[^0-9a-zA-Z_]+", "_", name.strip().lower())
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "field"
