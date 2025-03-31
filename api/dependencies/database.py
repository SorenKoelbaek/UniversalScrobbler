# -*- coding: utf-8 -*-
"""Dependencies for Database.

This module sets up an async SQLModel connection with Postgres using asyncpg.
Includes:
    - Async engine
    - Async sessionmaker
    - Dependency injection with yield
"""

import ssl
import urllib.parse
from typing import AsyncGenerator
from config import settings
from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel.sql.expression import Select, SelectOfScalar

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine, async_sessionmaker

# Settings
_local = settings.get("LOCAL")
_db_user = settings.get("USER")
_db_port = settings.get("PORT")
_db_host = settings.get("ENDPOINT")
_db_name = settings.get("DB_NAME")
_db_pass = settings.get("DB_PASS")

# Build async connection string
_local_postgres_connect_string = (
    f"postgresql+asyncpg://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
)
_local_sync_postgres_connect_string = (
	f"postgresql+pg8000://{_db_user}:{_db_pass}@{_db_host}:{_db_port}/{_db_name}"
)

def get_sync_engine(local: bool) -> Engine:
	"""Return Engine for Database.

	Args:
	    local (bool): Specifies if it should return a local database.

	Returns:
	    Engine (SQLModel._engine.Engine): Database engine.

	"""
	if local:
		db_url = _local_sync_postgres_connect_string
		engine = create_engine(db_url, echo=False)

	return engine

# Create async engine and sessionmaker
engine: AsyncEngine = create_async_engine(_local_postgres_connect_string, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Async session dependency for FastAPI
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session

# Optional utility for SQLModel performance
def set_inherit_cache():
    """Enable query caching for SQLModel to avoid performance warnings."""
    SelectOfScalar.inherit_cache = True  # type: ignore
    Select.inherit_cache = True  # type: ignore

def get_async_engine() -> AsyncEngine:
    """Return the async engine instance for use outside dependency injection."""
    return engine
