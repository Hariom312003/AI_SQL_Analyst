"""All REST endpoints in one consolidated router, matching this project's
flat layout (main.py just mounts this one router; no per-resource file
split / no versioned sub-package)."""
from __future__ import annotations

import uuid
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from loguru import logger
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.agents.dashboard_agent import build_dashboard_spec
from backend.agents.memory_agent import load_history
from backend.charts.plotly_chart import build_figure, figure_to_dict
from backend.database.ingestion import ingest_csv
from backend.database.models import (
    Conversation,
    ConversationMessage,
    Dataset,
    DatasetColumn,
    QueryHistory,
)
from backend.database.postgres import get_db, sync_engine
from backend.exceptions import DatasetNotFoundError, IngestionError
from backend.profiling.profiler import profile_dataframe
from backend.rag.retriever import rebuild_schema_index
from backend.schemas import (
    ChatRequest,
    ChatResponse,
    ColumnDescriptionUpdate,
    DatasetOut,
    DatasetProfileOut,
)

router = APIRouter()


def get_workflow(request: Request) -> Any:
    """Dependency-injects the compiled LangGraph workflow that main.py builds
    once at startup and stores on app.state -- avoids rebuilding the graph
    per-request, and (unlike a bare module-level global) is overridable in
    tests via `app.dependency_overrides[get_workflow] = ...`."""
    return request.app.state.workflow


# --------------------------------------------------------------- Health --
@router.get("/health")
async def health():
    return {"status": "ok"}


# ------------------------------------------------------------- Datasets --
@router.post("/datasets/upload", response_model=DatasetOut, status_code=201)
async def upload_dataset(file: UploadFile = File(...), db: AsyncSession = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only CSV files are supported in this phase.")

    raw = await file.read()
    dataset_name = file.filename.rsplit(".", 1)[0]

    try:
        result = ingest_csv(raw, dataset_name, sync_engine)
    except Exception as exc:
        raise IngestionError(f"Failed to ingest '{file.filename}': {exc}") from exc

    dataset = Dataset(
        id=uuid.uuid4(),
        name=dataset_name,
        original_filename=file.filename,
        table_name=result.table_name,
        row_count=result.row_count,
    )
    db.add(dataset)
    await db.flush()

    for col in result.columns:
        db.add(
            DatasetColumn(
                id=uuid.uuid4(),
                dataset_id=dataset.id,
                column_name=col["column_name"],
                inferred_dtype=col["inferred_dtype"],
                sql_type=col["sql_type"],
                sample_values=col["sample_values"],
                description=col["description"],
            )
        )
    await db.commit()
    await db.refresh(dataset)

    rebuild_schema_index()
    logger.info("Ingested dataset '{}' -> table '{}' ({} rows)", dataset.name, dataset.table_name, dataset.row_count)
    return dataset


@router.get("/datasets", response_model=list[DatasetOut])
async def list_datasets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Dataset))
    return result.scalars().all()


@router.get("/datasets/{dataset_id}/profile", response_model=DatasetProfileOut)
async def get_profile(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    dataset = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not dataset:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    df = pd.read_sql_table(dataset.table_name, con=sync_engine)
    return {"dataset_id": dataset_id, "profile": profile_dataframe(df)}


@router.get("/datasets/{dataset_id}/dashboard")
async def get_dashboard(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    dataset = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not dataset:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    df = pd.read_sql_table(dataset.table_name, con=sync_engine)
    spec = build_dashboard_spec(dataset.table_name, df)
    for chart in spec["charts"]:
        fig = build_figure(chart)
        chart["plotly_figure"] = figure_to_dict(fig) if fig else None
    return spec


@router.get("/datasets/{dataset_id}/preview")
async def get_preview(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    import numpy as np
    dataset = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not dataset:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    df = pd.read_sql_table(dataset.table_name, con=sync_engine)
    preview_df = df.head(20)
    rows = preview_df.replace({pd.NA: None, np.nan: None}).to_dict(orient="records")
    return {"dataset_id": dataset_id, "rows": rows}


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    dataset = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not dataset:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    
    table_name = dataset.table_name
    try:
        await db.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
    except Exception as exc:
        logger.warning("Failed to drop table '{}' during deletion: {}", table_name, exc)
        
    await db.delete(dataset)
    await db.commit()
    
    rebuild_schema_index()
    logger.info("Deleted dataset '{}' and dropped table '{}'", dataset.name, table_name)
    return {"status": "success", "message": f"Dataset {dataset_id} deleted."}


@router.patch("/datasets/{dataset_id}/columns/{column_name}", response_model=DatasetOut)
async def update_column_description(
    dataset_id: uuid.UUID,
    column_name: str,
    payload: ColumnDescriptionUpdate,
    db: AsyncSession = Depends(get_db),
):
    dataset = (await db.execute(select(Dataset).where(Dataset.id == dataset_id))).scalar_one_or_none()
    if not dataset:
        raise DatasetNotFoundError(f"Dataset {dataset_id} not found.")
    column = (
        await db.execute(
            select(DatasetColumn).where(
                DatasetColumn.dataset_id == dataset_id, DatasetColumn.column_name == column_name
            )
        )
    ).scalar_one_or_none()
    if not column:
        raise HTTPException(404, f"Column '{column_name}' not found on this dataset.")

    column.description = payload.description
    await db.commit()
    await db.refresh(dataset)
    rebuild_schema_index()
    return dataset


# ----------------------------------------------------------------- Chat --
@router.post("/chat/ask", response_model=ChatResponse)
async def ask(
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db),
    workflow: Any = Depends(get_workflow),
):
    conversation_id = payload.conversation_id or uuid.uuid4()
    conversation = (
        await db.execute(select(Conversation).where(Conversation.id == conversation_id))
    ).scalar_one_or_none()
    if conversation is None:
        conversation = Conversation(id=conversation_id, title=payload.question[:80])
        db.add(conversation)
        await db.flush()

    history_rows = (
        await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conversation_id)
            .order_by(ConversationMessage.created_at)
        )
    ).scalars().all()
    history = load_history(history_rows)

    initial_state = {"question": payload.question, "history": history, "conversation_id": str(conversation_id)}

    try:
        final_state = workflow.invoke(initial_state)
    except Exception as exc:
        raise HTTPException(500, f"Agent workflow failed: {exc}") from exc

    db.add(ConversationMessage(id=uuid.uuid4(), conversation_id=conversation_id, role="user", content=payload.question))
    db.add(
        ConversationMessage(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            role="assistant",
            content=final_state.get("explanation", ""),
            generated_sql=final_state.get("sql"),
        )
    )
    db.add(
        QueryHistory(
            id=uuid.uuid4(),
            conversation_id=conversation_id,
            question=payload.question,
            generated_sql=final_state.get("sql", ""),
            is_valid=final_state.get("is_valid", False),
            repair_attempts=final_state.get("repair_attempts", 0),
            row_count=final_state.get("row_count"),
            error=final_state.get("execution_error"),
        )
    )
    await db.commit()

    chart_spec = final_state.get("chart_spec", {})
    fig = build_figure(chart_spec)

    return ChatResponse(
        conversation_id=conversation_id,
        resolved_question=final_state.get("resolved_question", payload.question),
        sql=final_state.get("sql", ""),
        columns=final_state.get("result_columns", []),
        rows=final_state.get("result_rows", []),
        row_count=final_state.get("row_count", 0),
        explanation=final_state.get("explanation", ""),
        chart_spec=chart_spec,
        plotly_figure=figure_to_dict(fig) if fig else None,
        validation_errors=final_state.get("validation_errors", []),
        execution_error=final_state.get("execution_error"),
    )
