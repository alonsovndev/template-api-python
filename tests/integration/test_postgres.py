from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.config import Settings
from app.config.models import PersistenceSettings
from app.main import create_app
from tests.support.items.domain.item import Item
from tests.support.items.infrastructure.postgres_repository import PostgreSQLItemRepository
from tests.support.postgres import test_connection_settings as connection_settings
from tests.support.postgres import test_database as isolated_database

pytestmark = pytest.mark.postgres
ITEM_IDENTIFIER = UUID("c434c22d-cce4-4b2b-81bd-8b4fb012e534")


async def test_repository_flushes_without_committing_then_commit_is_visible() -> None:
    async with isolated_database() as engine:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        item = Item(ITEM_IDENTIFIER, "Committed")
        async with sessions() as writer, writer.begin():
            await PostgreSQLItemRepository(writer).add(item)
            async with sessions() as reader:
                assert await PostgreSQLItemRepository(reader).get(ITEM_IDENTIFIER) is None
        async with sessions() as reader:
            assert await PostgreSQLItemRepository(reader).get(ITEM_IDENTIFIER) == item


async def test_failed_operation_rolls_back_its_write() -> None:
    async with isolated_database() as engine:
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        with pytest.raises(ValueError, match="abort operation"):
            async with sessions() as writer, writer.begin():
                await PostgreSQLItemRepository(writer).add(Item(ITEM_IDENTIFIER, "Rolled back"))
                raise ValueError("abort operation")
        async with sessions() as reader:
            assert await PostgreSQLItemRepository(reader).get(ITEM_IDENTIFIER) is None


async def test_database_enforces_nonblank_names() -> None:
    async with isolated_database() as engine:
        with pytest.raises(IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    text("INSERT INTO items (identifier, name) VALUES (:identifier, :name)"),
                    {"identifier": ITEM_IDENTIFIER, "name": "   "},
                )


def test_postgresql_api_readiness_with_real_configuration() -> None:
    settings = Settings(
        environment="test",
        persistence=PersistenceSettings(
            driver="postgresql",
            postgres=connection_settings(),
        ),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}
