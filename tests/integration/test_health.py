from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.config.models import Environment, PersistenceSettings, PostgreSQLSettings
from app.container import ApplicationContainer, get_readiness_use_case
from app.features.health.application.check_readiness import CheckReadiness
from app.main import create_app


class UnavailableProbe:
    async def is_ready(self) -> bool:
        return False


def test_memory_health_and_readiness_contracts() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        assert client.get("/health").json() == {"status": "ok"}
        response = client.get("/health/ready")
        assert response.status_code == 200
        assert response.json() == {"status": "ready"}


def test_liveness_stays_healthy_when_readiness_fails() -> None:
    application = create_app(Settings(environment="test"))
    application.dependency_overrides[get_readiness_use_case] = lambda: CheckReadiness(
        UnavailableProbe()
    )
    with TestClient(application) as client:
        assert client.get("/health").status_code == 200
        response = client.get("/health/ready")
        assert response.status_code == 503
        assert response.json() == {"status": "not_ready"}


@pytest.mark.parametrize(
    ("environment", "enabled"),
    [("local", True), ("container", True), ("dev", False), ("test", False), ("prod", False)],
)
def test_documentation_exposure_follows_profile(environment: Environment, enabled: bool) -> None:
    with TestClient(create_app(Settings(environment=environment))) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == (200 if enabled else 404)


def test_no_business_routes_are_registered() -> None:
    schema = create_app(Settings()).openapi()
    assert set(schema["paths"]) == {"/health", "/health/ready"}
    assert "503" in schema["paths"]["/health/ready"]["get"]["responses"]


def test_application_instances_have_independent_containers_and_overrides() -> None:
    first = create_app(Settings(environment="test"))
    second = create_app(Settings(environment="test"))
    first.dependency_overrides[get_readiness_use_case] = lambda: CheckReadiness(UnavailableProbe())
    with TestClient(first) as first_client, TestClient(second) as second_client:
        assert first.state.container is not second.state.container
        assert first_client.get("/health/ready").status_code == 503
        assert second_client.get("/health/ready").status_code == 200
    assert first.state.container.readiness is None
    assert second.state.container.readiness is None


def test_database_engine_is_disposed_after_lifespan(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = AsyncMock()
    monkeypatch.setattr("app.container.create_database_engine", lambda _: engine)
    settings = Settings(
        persistence=PersistenceSettings(
            driver="postgresql",
            postgres=PostgreSQLSettings(
                host="localhost",
                username="app",
                database="app",
                password=SecretStr("<test-password>"),
            ),
        )
    )
    application = create_app(settings)
    with TestClient(application):
        container: ApplicationContainer = application.state.container
        assert container.engine is engine
        assert container.session_factory is not None
    engine.dispose.assert_awaited_once()
    assert container.engine is None
    assert container.session_factory is None
