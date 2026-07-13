"""Application-specific exceptions and their FastAPI exception handlers."""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from loguru import logger


class DatasetNotFoundError(Exception):
    pass


class IngestionError(Exception):
    pass


async def dataset_not_found_handler(request: Request, exc: DatasetNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": str(exc) or "Dataset not found."})


async def ingestion_error_handler(request: Request, exc: IngestionError) -> JSONResponse:
    logger.warning("Ingestion failed: {}", exc)
    return JSONResponse(status_code=422, content={"detail": str(exc)})


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on {}", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
