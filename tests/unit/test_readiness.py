import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast
from unittest.mock import Mock

import pytest
from asyncpg import PostgresError
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.features.health.infrastructure.probes import PostgreSQLReadinessProbe


@pytest.mark.parametrize(
    "failure",
    [
        OSError("<connection-error>"),
        PostgresError("<database-error>"),
        SQLAlchemyError("<query-error>"),
    ],
)
async def test_database_errors_return_unavailable(failure: Exception) -> None:
    engine = Mock(spec=AsyncEngine)
    engine.connect.side_effect = failure
    assert await PostgreSQLReadinessProbe(cast(AsyncEngine, engine)).is_ready() is False


async def test_readiness_bounds_a_stalled_connection() -> None:
    @asynccontextmanager
    async def stalled_connection() -> AsyncIterator[None]:
        await asyncio.sleep(10)
        yield None

    engine = Mock(spec=AsyncEngine)
    engine.connect.return_value = stalled_connection()
    async with asyncio.timeout(3):
        assert await PostgreSQLReadinessProbe(cast(AsyncEngine, engine)).is_ready() is False
