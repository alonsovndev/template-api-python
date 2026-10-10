from pydantic import SecretStr
from sqlalchemy.pool import NullPool

from app.config.models import PostgreSQLSettings
from app.shared.infrastructure.database import (
    connection_arguments,
    create_database_engine,
    database_url,
)


def settings_with(**overrides: str) -> PostgreSQLSettings:
    return PostgreSQLSettings(
        host="db.example.test",
        username="app",
        password=SecretStr("<test-password>"),
        database="app",
        **overrides,  # type: ignore[arg-type]
    )


def test_defaults_keep_the_plain_pooled_connection() -> None:
    settings = settings_with()
    assert connection_arguments(settings) == {}
    assert database_url(settings).query == {}
    assert not isinstance(create_database_engine(settings).pool, NullPool)


def test_ssl_mode_is_passed_to_asyncpg() -> None:
    assert connection_arguments(settings_with(ssl_mode="require")) == {"ssl": "require"}
    assert connection_arguments(settings_with(ssl_mode="disable")) == {}


def test_null_pool_mode_disables_prepared_statement_reuse_for_poolers() -> None:
    settings = settings_with(pool_mode="null")
    url = database_url(settings)
    assert url.query == {"prepared_statement_cache_size": "0"}
    arguments = connection_arguments(settings)
    assert arguments["statement_cache_size"] == 0
    name_function = arguments["prepared_statement_name_func"]
    assert name_function() != name_function()
    assert isinstance(create_database_engine(settings).pool, NullPool)
