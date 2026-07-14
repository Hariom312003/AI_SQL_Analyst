"""FastAPI application entrypoint. Run with:
    uvicorn backend.api.main:app --reload
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from backend.agents.workflow import build_workflow
from backend.api.routes import router
from backend.config import get_settings
from backend.exceptions import (
    DatasetNotFoundError,
    IngestionError,
    dataset_not_found_handler,
    ingestion_error_handler,
    unhandled_exception_handler,
)
from backend.llm.factory import get_llm_provider
from backend.logging_config import configure_logging
from backend.rag.retriever import rebuild_schema_index

settings = get_settings()
configure_logging("DEBUG" if settings.debug else "INFO")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting {} (env={})", settings.app_name, settings.environment)
    
    # Run Alembic migrations on startup
    try:
        from alembic.config import Config
        from alembic import command
        logger.info("Running database migrations via Alembic...")
        alembic_cfg = Config("alembic.ini")
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations completed successfully.")
    except Exception as e:
        logger.warning(f"Alembic auto-migration failed or skipped: {e}")

    try:
        rebuild_schema_index()
    except Exception:
        logger.exception("Schema index rebuild failed at startup (fine if no datasets yet).")

    # Built once per process and shared across requests via app.state (not a
    # module-level global) -- lets tests override it with
    # `app.dependency_overrides` and keeps construction order explicit.
    app.state.llm_provider = get_llm_provider()
    app.state.workflow = build_workflow(app.state.llm_provider)
    logger.info("LLM provider ready: {}", type(app.state.llm_provider).__name__)

    yield
    logger.info("Shutting down {}", settings.app_name)


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.environment == "local" else [],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_exception_handler(DatasetNotFoundError, dataset_not_found_handler)
app.add_exception_handler(IngestionError, ingestion_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(router, prefix=settings.api_v1_prefix)
