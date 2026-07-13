"""Central application configuration, loaded from environment variables / .env.

Kept as a single flat module (rather than backend/core/config.py) to match
this project's flatter layout -- everything hangs directly off backend/.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    app_name: str = "AI SQL Analyst"
    api_v1_prefix: str = "/api/v1"
    environment: Literal["local", "test", "staging", "production"] = "local"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://sql_analyst:sql_analyst@localhost:5432/sql_analyst"
    sync_database_url: str = "postgresql+psycopg2://sql_analyst:sql_analyst@localhost:5432/sql_analyst"

    # LLM
    llm_provider: Literal["gemini", "anthropic", "fake"] = "fake"
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-5"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-flash"
    llm_max_retries: int = 2

    # RAG / vector store
    vector_db_path: str = "./chroma_db"

    # Security (wired up in a later phase)
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # Agent behaviour
    sql_repair_max_attempts: int = 2
    max_result_rows: int = 1000


@lru_cache
def get_settings() -> Settings:
    return Settings()
