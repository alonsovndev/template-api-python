import asyncio

from asyncpg import PostgresError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine


class MemoryReadinessProbe:
    async def is_ready(self) -> bool:
        return True


class PostgreSQLReadinessProbe:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def is_ready(self) -> bool:
        try:
            async with asyncio.timeout(2), self._engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except (SQLAlchemyError, PostgresError, OSError, TimeoutError):
            return False
