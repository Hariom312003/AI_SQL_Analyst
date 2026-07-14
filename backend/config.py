"""Central application configuration, loaded from environment variables / .env.

Kept as a single flat module (rather than backend/core/config.py) to match
this project's flatter layout -- everything hangs directly off backend/.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import model_validator
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

    @model_validator(mode="after")
    def validate_database_urls(self) -> Settings:
        # Convert postgres:// or postgresql:// to postgresql+asyncpg://
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            elif "postgresql+asyncpg" not in url:
                if "postgresql+" in url:
                    parts = url.split("://", 1)
                    parts[0] = "postgresql+asyncpg"
                    url = "://".join(parts)
            # Replace sslmode= with ssl= for asyncpg compatibility
            if "sslmode=" in url:
                url = url.replace("sslmode=", "ssl=", 1)
            self.database_url = url

        # Convert postgres:// or postgresql:// to postgresql+psycopg2://
        if self.sync_database_url:
            url = self.sync_database_url
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+psycopg2://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
            elif "postgresql+psycopg2" not in url:
                if "postgresql+" in url:
                    parts = url.split("://", 1)
                    parts[0] = "postgresql+psycopg2"
                    url = "://".join(parts)
            # Ensure sync connection has sslmode= (replace ssl= with sslmode= if user passed ssl=)
            if "ssl=" in url and "sslmode=" not in url:
                url = url.replace("ssl=", "sslmode=", 1)
            self.sync_database_url = url
            
        return self

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
