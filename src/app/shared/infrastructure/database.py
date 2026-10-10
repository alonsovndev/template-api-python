from typing import Any
from uuid import uuid4

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.config.models import PostgreSQLSettings


class Base(DeclarativeBase):
    pass


def database_url(settings: PostgreSQLSettings) -> URL:
    # SQLAlchemy reads this cache size from the URL; asyncpg's own cache is a connect argument.
    pooler_query = {"prepared_statement_cache_size": "0"} if settings.pool_mode == "null" else {}
    return URL.create(
        "postgresql+asyncpg",
        username=settings.username,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database=settings.database,
        query=pooler_query,
    )


def connection_arguments(settings: PostgreSQLSettings) -> dict[str, Any]:
    arguments: dict[str, Any] = {}
    if settings.ssl_mode != "disable":
        arguments["ssl"] = settings.ssl_mode
    if settings.pool_mode == "null":
        # Transaction-mode poolers (Supabase, PgBouncer) reject asyncpg's named prepared statements.
        arguments["statement_cache_size"] = 0
        arguments["prepared_statement_name_func"] = lambda: f"__asyncpg_{uuid4()}__"
    return arguments


def create_database_engine(settings: PostgreSQLSettings) -> AsyncEngine:
    pool_options: dict[str, Any] = {"poolclass": NullPool} if settings.pool_mode == "null" else {}
    return create_async_engine(
        database_url(settings),
        pool_pre_ping=True,
        hide_parameters=True,
        connect_args=connection_arguments(settings),
        **pool_options,
    )
