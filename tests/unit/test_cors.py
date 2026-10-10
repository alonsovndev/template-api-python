from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.config import ConfigurationError, ConfigurationPaths, Settings, load_settings
from app.config.models import CorsSettings
from app.main import create_app

ORIGIN = "https://app.example.test"


def preflight(client: TestClient, origin: str) -> dict[str, str]:
    response = client.options(
        "/health",
        headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
    )
    return dict(response.headers)


def test_cors_is_disabled_by_default() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        assert "access-control-allow-origin" not in preflight(client, ORIGIN)
        assert (
            "access-control-allow-origin"
            not in client.get("/health", headers={"Origin": ORIGIN}).headers
        )


def test_listed_origin_is_allowed_and_others_are_not() -> None:
    settings = Settings(environment="test", cors=CorsSettings(allowed_origins=(ORIGIN,)))
    with TestClient(create_app(settings)) as client:
        assert preflight(client, ORIGIN)["access-control-allow-origin"] == ORIGIN
        assert "access-control-allow-origin" not in preflight(client, "https://other.example.test")
        assert "access-control-allow-credentials" not in preflight(client, ORIGIN)


def test_origins_come_from_a_comma_separated_variable(tmp_path: Path) -> None:
    paths = ConfigurationPaths(environment_file=tmp_path / ".env")
    settings = load_settings(
        paths, {"CORS_ALLOWED_ORIGINS": f" {ORIGIN} , https://second.example.test ,"}
    )
    assert settings.cors.allowed_origins == (ORIGIN, "https://second.example.test")


def test_wildcard_origin_is_rejected() -> None:
    with pytest.raises(ValidationError):
        CorsSettings(allowed_origins=("*",))


@pytest.mark.parametrize(
    "origin",
    ["https://app.example.test/", "app.example.test", "https://app.example.test/path", "*"],
)
def test_malformed_origins_are_rejected(origin: str) -> None:
    with pytest.raises(ValidationError):
        CorsSettings(allowed_origins=(origin,))


def test_wildcard_is_rejected_through_the_environment(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError, match="cors"):
        load_settings(
            ConfigurationPaths(environment_file=tmp_path / ".env"), {"CORS_ALLOWED_ORIGINS": "*"}
        )
