from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Settings
from app.features.health.application.check_readiness import CheckReadiness
from app.features.health.infrastructure.probes import MemoryReadinessProbe, PostgreSQLReadinessProbe
from app.shared.infrastructure.database import create_database_engine


class ApplicationContainer:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine | None = None
        self.session_factory: async_sessionmaker[AsyncSession] | None = None
        self.readiness: CheckReadiness | None = None

    def start(self) -> None:
        if self.settings.persistence.driver == "postgresql":
            self.engine = create_database_engine(self.settings.persistence.postgres)
            self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
            self.readiness = CheckReadiness(PostgreSQLReadinessProbe(self.engine))
        else:
            self.readiness = CheckReadiness(MemoryReadinessProbe())

    async def close(self) -> None:
        if self.engine is not None:
            await self.engine.dispose()
        self.engine = None
        self.session_factory = None
        self.readiness = None


def get_readiness_use_case(request: Request) -> CheckReadiness:
    container = cast(ApplicationContainer, request.app.state.container)
    if container.readiness is None:
        raise RuntimeError("Application lifespan has not started")
    return container.readiness
