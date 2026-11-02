import asyncio

from alembic import context
from sqlalchemy import Connection, MetaData, pool
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import ConfigurationError, load_settings
from app.shared.infrastructure.database import Base, connection_arguments, database_url

configuration = context.config
target_metadata: MetaData = configuration.attributes.get("target_metadata", Base.metadata)


def run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_online_migrations() -> None:
    settings = load_settings()
    if settings.persistence.driver != "postgresql":
        raise ConfigurationError("Alembic requires PERSISTENCE_DRIVER=postgresql")
    engine = create_async_engine(
        database_url(settings.persistence.postgres),
        poolclass=pool.NullPool,
        hide_parameters=True,
        connect_args=connection_arguments(settings.persistence.postgres),
    )
    try:
        async with engine.connect() as connection:
            await connection.run_sync(run_migrations)
    finally:
        await engine.dispose()


def run_offline_migrations() -> None:
    settings = load_settings()
    if settings.persistence.driver != "postgresql":
        raise ConfigurationError("Alembic requires PERSISTENCE_DRIVER=postgresql")
    context.configure(
        url=database_url(settings.persistence.postgres),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_offline_migrations()
elif (supplied_connection := configuration.attributes.get("connection")) is not None:
    run_migrations(supplied_connection)
else:
    asyncio.run(run_online_migrations())
