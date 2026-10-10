import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import Settings, load_settings
from app.container import ApplicationContainer
from app.features.health.presentation.router import router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        container = ApplicationContainer(settings)
        application.state.container = container
        logging.basicConfig(
            level=settings.logging.level, format="%(levelname)s %(name)s %(message)s"
        )
        try:
            container.start()
            yield
        finally:
            await container.close()

    docs_enabled = settings.environment in {"local", "container"}
    application = FastAPI(
        title=settings.app.name,
        version=settings.app.version,
        lifespan=lifespan,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
    )
    application.include_router(router)
    return application
