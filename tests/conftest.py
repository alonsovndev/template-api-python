from collections.abc import AsyncIterator
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support.items.domain.repository import ItemRepository
from tests.support.items.infrastructure.memory_repository import MemoryItemRepository
from tests.support.items.infrastructure.postgres_repository import PostgreSQLItemRepository
from tests.support.postgres import test_database


@pytest.fixture(
    params=["memory", pytest.param("postgresql", marks=pytest.mark.postgres)],
)
async def item_repository(request: pytest.FixtureRequest) -> AsyncIterator[ItemRepository]:
    driver = cast(str, request.param)
    if driver == "memory":
        yield MemoryItemRepository()
    else:
        async with test_database() as engine, engine.connect() as connection:
            transaction = await connection.begin()
            try:
                async with AsyncSession(
                    bind=connection, join_transaction_mode="create_savepoint"
                ) as session:
                    yield PostgreSQLItemRepository(session)
            finally:
                await transaction.rollback()
