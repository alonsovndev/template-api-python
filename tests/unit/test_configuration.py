import os
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import ConfigurationError, ConfigurationPaths, Settings, load_settings


def paths_for(tmp_path: Path) -> ConfigurationPaths:
    return ConfigurationPaths(environment_file=tmp_path / ".env")


def test_defaults_to_local_memory_without_a_database(tmp_path: Path) -> None:
    settings = load_settings(paths_for(tmp_path), {})
    assert settings.environment == "local"
    assert settings.persistence.driver == "memory"


@pytest.mark.parametrize(
    ("profile", "driver"),
    [
        ("local", "memory"),
        ("test", "memory"),
        ("dev", "postgresql"),
        ("container", "postgresql"),
        ("prod", "postgresql"),
    ],
)
def test_selects_each_environment_profile(tmp_path: Path, profile: str, driver: str) -> None:
    settings = load_settings(
        paths_for(tmp_path),
        {
            "APP_ENV": profile,
            "POSTGRES_HOST": "localhost",
            "POSTGRES_USER": "app",
            "POSTGRES_DB": "app",
            "POSTGRES_PASSWORD": "<test-password>",
        },
    )
    assert settings.environment == profile
    assert settings.persistence.driver == driver


def test_process_values_override_dotenv_without_mutating_os_environ(tmp_path: Path) -> None:
    (tmp_path / ".env").write_text("APP_ENV=test\nAPP_NAME=file-name\n", encoding="utf-8")
    previous_environment = dict(os.environ)
    settings = load_settings(paths_for(tmp_path), {"APP_NAME": "process-name"})
    assert settings.environment == "test"
    assert settings.app.name == "process-name"
    assert dict(os.environ) == previous_environment


@pytest.mark.parametrize("process_selects_prod", [True, False])
def test_production_ignores_dotenv_values(tmp_path: Path, process_selects_prod: bool) -> None:
    (tmp_path / ".env").write_text("APP_ENV=prod\nAPP_NAME=ignored-name\n", encoding="utf-8")
    environment = {"PERSISTENCE_DRIVER": "memory"}
    if process_selects_prod:
        environment["APP_ENV"] = "prod"
    settings = load_settings(paths_for(tmp_path), environment)
    assert settings.environment == "prod"
    assert settings.app.name == "template-api-python"


def test_can_use_memory_in_container_without_database_credentials(tmp_path: Path) -> None:
    settings = load_settings(
        paths_for(tmp_path), {"APP_ENV": "container", "PERSISTENCE_DRIVER": "memory"}
    )
    assert settings.persistence.driver == "memory"


def test_postgresql_requires_password(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="persistence"):
        load_settings(paths_for(tmp_path), {"PERSISTENCE_DRIVER": "postgresql"})


def test_production_requires_explicit_database_identity(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="persistence"):
        load_settings(
            paths_for(tmp_path), {"APP_ENV": "prod", "POSTGRES_PASSWORD": "<test-password>"}
        )


def test_pydantic_coerces_environment_port(tmp_path: Path) -> None:
    settings = load_settings(paths_for(tmp_path), {"POSTGRES_PORT": "5440"})
    assert settings.persistence.postgres.port == 5440


@pytest.mark.parametrize("profile", ["../outside", "staging", ""])
def test_unknown_profile_cannot_select_an_arbitrary_path(tmp_path: Path, profile: str) -> None:
    with pytest.raises(ConfigurationError, match="APP_ENV must"):
        load_settings(paths_for(tmp_path), {"APP_ENV": profile})


def test_invalid_environment_values_are_not_in_errors(tmp_path: Path) -> None:
    sensitive_value = "<sensitive-config-value>"
    with pytest.raises(ConfigurationError) as error:
        load_settings(paths_for(tmp_path), {"POSTGRES_PORT": sensitive_value})
    assert "persistence.postgres.port" in str(error.value)
    assert sensitive_value not in str(error.value)


def test_settings_and_nested_models_are_immutable() -> None:
    settings = Settings()
    with pytest.raises(ValidationError, match="frozen"):
        settings.environment = "test"
    with pytest.raises(ValidationError, match="frozen"):
        settings.app.name = "changed"


@pytest.mark.parametrize(
    "content",
    [
        "app: [",
        "!!python/object/apply:os.system ['false']",
        "- a-list",
        "environment: prod",
        "unknown: field",
        "app:\n  name: !ENV ${BROKEN",
        "app:\n  name: !ENV ${REQUIRED}",
    ],
)
def test_rejects_invalid_or_unsafe_yaml(tmp_path: Path, content: str) -> None:
    (tmp_path / "config_local.yml").write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(ConfigurationPaths(tmp_path, tmp_path / ".env"), {})


def test_missing_profile_file_fails_clearly(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="profile local"):
        load_settings(ConfigurationPaths(tmp_path, tmp_path / ".env"), {})


def test_invalid_utf8_dotenv_raises_a_safe_configuration_error(tmp_path: Path) -> None:
    (tmp_path / ".env").write_bytes(b"APP_NAME=\xff")
    with pytest.raises(ConfigurationError, match="Could not read the environment file"):
        load_settings(paths_for(tmp_path), {})


def test_interpolation_supports_embedded_values_and_colons_in_defaults(tmp_path: Path) -> None:
    (tmp_path / "config_local.yml").write_text(
        "app:\n  name: !ENV '${PREFIX:service}-${SUFFIX:localhost:8080}'\n", encoding="utf-8"
    )
    settings = load_settings(ConfigurationPaths(tmp_path, tmp_path / ".env"), {"PREFIX": "example"})
    assert settings.app.name == "example-localhost:8080"


def test_inserted_values_are_not_interpreted_again(tmp_path: Path) -> None:
    settings = load_settings(paths_for(tmp_path), {"APP_NAME": "literal-${name}"})
    assert settings.app.name == "literal-${name}"


def test_independent_loads_do_not_leak_values(tmp_path: Path) -> None:
    first = load_settings(paths_for(tmp_path), {"APP_NAME": "first"})
    second = load_settings(paths_for(tmp_path), {"APP_NAME": "second"})
    assert first.app.name == "first"
    assert second.app.name == "second"


def test_credentials_json_supplies_the_database_user_and_password(tmp_path: Path) -> None:
    settings = load_settings(
        paths_for(tmp_path),
        {
            "APP_ENV": "prod",
            "POSTGRES_HOST": "db.example.test",
            "POSTGRES_DB": "app",
            "POSTGRES_CREDENTIALS_JSON": '{"username": "master", "password": "<test-password>"}',
        },
    )
    postgres = settings.persistence.postgres
    assert postgres.username == "master"
    assert postgres.password.get_secret_value() == "<test-password>"


@pytest.mark.parametrize(
    "credentials", ["not json", "[]", '{"username": "master"}', '{"password": 1}']
)
def test_invalid_credentials_json_fails_without_echoing_the_value(
    tmp_path: Path, credentials: str
) -> None:
    with pytest.raises(ConfigurationError) as error:
        load_settings(
            paths_for(tmp_path),
            {
                "APP_ENV": "prod",
                "POSTGRES_HOST": "db.example.test",
                "POSTGRES_DB": "app",
                "POSTGRES_CREDENTIALS_JSON": credentials,
            },
        )
    assert "persistence.postgres" in str(error.value)
    assert credentials not in str(error.value)


SECRET_ARN = "arn:aws:secretsmanager:us-east-1:123456789012:secret:app-database-AbCdEf"
SECRET_JSON = '{"username": "app", "password": "<test-password>"}'


def test_credentials_are_read_from_the_secret_named_by_arn(tmp_path: Path) -> None:
    requested: list[str] = []

    def read_secret(secret_arn: str) -> str:
        requested.append(secret_arn)
        return SECRET_JSON

    settings = load_settings(
        paths_for(tmp_path),
        {
            "APP_ENV": "prod",
            "POSTGRES_HOST": "db.example.test",
            "POSTGRES_DB": "app",
            "POSTGRES_CREDENTIALS_SECRET_ARN": SECRET_ARN,
        },
        read_secret,
    )
    assert requested == [SECRET_ARN]
    assert settings.persistence.postgres.username == "app"
    assert settings.persistence.postgres.password.get_secret_value() == "<test-password>"


def test_explicit_credentials_json_skips_the_secret_lookup(tmp_path: Path) -> None:
    def read_secret(secret_arn: str) -> str:
        raise AssertionError("The secret must not be read")

    settings = load_settings(
        paths_for(tmp_path),
        {
            "APP_ENV": "prod",
            "POSTGRES_HOST": "db.example.test",
            "POSTGRES_DB": "app",
            "POSTGRES_CREDENTIALS_JSON": SECRET_JSON,
            "POSTGRES_CREDENTIALS_SECRET_ARN": SECRET_ARN,
        },
        read_secret,
    )
    assert settings.persistence.postgres.username == "app"


def test_secret_lookup_failure_stops_startup_without_details(tmp_path: Path) -> None:
    def read_secret(secret_arn: str) -> str:
        raise RuntimeError(f"denied for {secret_arn} with <sensitive-detail>")

    with pytest.raises(ConfigurationError) as error:
        load_settings(
            paths_for(tmp_path),
            {
                "APP_ENV": "prod",
                "POSTGRES_HOST": "db.example.test",
                "POSTGRES_DB": "app",
                "POSTGRES_CREDENTIALS_SECRET_ARN": SECRET_ARN,
            },
            read_secret,
        )
    assert "credentials secret (RuntimeError)" in str(error.value)
    assert "<sensitive-detail>" not in str(error.value)


@pytest.mark.parametrize(
    "environment",
    [
        {"APP_ENV": "local"},
        {"APP_ENV": "test"},
        {"APP_ENV": "prod", "PERSISTENCE_DRIVER": "memory"},
    ],
)
def test_secret_is_not_read_when_credentials_are_unused(
    tmp_path: Path, environment: dict[str, str]
) -> None:
    def read_secret(secret_arn: str) -> str:
        raise AssertionError("The secret must not be read")

    load_settings(
        paths_for(tmp_path),
        {"POSTGRES_CREDENTIALS_SECRET_ARN": SECRET_ARN, **environment},
        read_secret,
    )
