import pytest

from tests.support.postgres import test_connection_settings as connection_settings


def test_postgres_tests_reject_production_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(RuntimeError, match="APP_ENV=test"):
        connection_settings()


def test_postgres_tests_cannot_fall_back_to_application_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.delenv("TEMPLATE_TEST_PROJECT", raising=False)
    monkeypatch.setenv("POSTGRES_HOST", "production.example")
    monkeypatch.setenv("DATABASE_URL", "postgresql://production.example/app")
    with pytest.raises(RuntimeError, match="disposable test runner"):
        connection_settings()
