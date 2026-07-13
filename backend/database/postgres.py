"""Database connectivity.

Two engines are kept side by side deliberately:
- an ASYNC engine (asyncpg) for FastAPI's normal request handling (ORM reads/
  writes for datasets, conversations, query history) -- scales better under
  concurrent load.
- a SYNC engine (psycopg2) specifically for pandas.DataFrame.to_sql() and
  dynamic-table DDL during CSV ingestion, and for the SQL agents' arbitrary
  read-only query execution. Pandas does not support async engines, and the
  agents' raw-SQL execution doesn't need to be async, so keeping this sync
  keeps that code far simpler.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from backend.config import get_settings

settings = get_settings()


class Base(DeclarativeBase):
    pass


engine = create_async_engine(settings.database_url, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

sync_engine = create_engine(settings.sync_database_url, echo=False, future=True)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
