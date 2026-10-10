from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config.models import PostgreSQLSettings


class Base(DeclarativeBase):
    pass


def database_url(settings: PostgreSQLSettings) -> URL:
    return URL.create(
        "postgresql+asyncpg",
        username=settings.username,
        password=settings.password.get_secret_value(),
        host=settings.host,
        port=settings.port,
        database=settings.database,
    )


def create_database_engine(settings: PostgreSQLSettings) -> AsyncEngine:
    return create_async_engine(database_url(settings), pool_pre_ping=True, hide_parameters=True)
