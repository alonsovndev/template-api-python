import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config
from pydantic import SecretStr
from sqlalchemy import Connection, text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.config.models import PostgreSQLSettings
from app.shared.infrastructure.database import create_database_engine
from tests.support.items.infrastructure.models import ExampleBase

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_connection_settings() -> PostgreSQLSettings:
    if os.environ.get("APP_ENV") != "test":
        raise RuntimeError("PostgreSQL tests require APP_ENV=test; use scripts/test_postgres.py")
    project = os.environ.get("TEMPLATE_TEST_PROJECT", "")
    port = os.environ.get("TEMPLATE_TEST_POSTGRES_PORT", "")
    password = os.environ.get("TEMPLATE_TEST_PASSWORD", "")
    if not project.startswith("template-api-test-") or not port.isdecimal() or not password:
        raise RuntimeError("PostgreSQL tests require the disposable test runner environment")
    return PostgreSQLSettings(
        host="127.0.0.1",
        port=int(port),
        username="template_test",
        password=SecretStr(password),
        database="template_api_test",
    )


def migration_configuration(include_example: bool = True) -> Config:
    configuration = Config(str(PROJECT_ROOT / "alembic.ini"))
    if include_example:
        configuration.set_main_option(
            "version_locations",
            os.pathsep.join(
                str(directory)
                for directory in (
                    PROJECT_ROOT / "alembic/versions",
                    PROJECT_ROOT / "tests/fixtures/alembic/versions",
                )
            ),
        )
        configuration.attributes["target_metadata"] = ExampleBase.metadata
    return configuration


def upgrade(connection: Connection, configuration: Config) -> None:
    configuration.attributes["connection"] = connection
    command.upgrade(configuration, "head")


def downgrade(connection: Connection, configuration: Config) -> None:
    configuration.attributes["connection"] = connection
    command.downgrade(configuration, "base")


@asynccontextmanager
async def test_database(include_example: bool = True) -> AsyncIterator[AsyncEngine]:
    engine = create_database_engine(test_connection_settings())
    configuration = migration_configuration(include_example)
    verified_database = False
    try:
        async with engine.begin() as connection:
            identity = (
                await connection.execute(text("SELECT current_database(), current_user"))
            ).one()
            if tuple(identity) != ("template_api_test", "template_test"):
                raise RuntimeError(
                    "Refusing to migrate a database outside the disposable test setup"
                )
            verified_database = True
            await connection.run_sync(upgrade, configuration)
        yield engine
    finally:
        try:
            if verified_database:
                async with engine.begin() as connection:
                    await connection.run_sync(downgrade, configuration)
        finally:
            await engine.dispose()
