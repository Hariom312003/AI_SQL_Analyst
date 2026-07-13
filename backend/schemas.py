"""Pydantic request/response models for the API layer.

Kept in one flat module (rather than a schemas/ package split by resource)
since routes.py itself is also a single consolidated file in this project's
layout -- this is the natural counterpart to it.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    original_filename: str
    table_name: str
    row_count: int
    created_at: datetime


class DatasetProfileOut(BaseModel):
    dataset_id: uuid.UUID
    profile: dict


class ColumnDescriptionUpdate(BaseModel):
    description: str


class ChatRequest(BaseModel):
    question: str
    conversation_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    resolved_question: str
    sql: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    explanation: str
    chart_spec: dict
    plotly_figure: dict | None = None
    validation_errors: list[str] = []
    execution_error: str | None = None
