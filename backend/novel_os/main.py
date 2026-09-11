from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from novel_os.api.agent_routes import router as agent_router
from novel_os.api.core_routes import router as core_router
from novel_os.api.errors import register_exception_handlers
from novel_os.api.health import router as health_router
from novel_os.api.middleware import RequestContextMiddleware
from novel_os.api.schemas import ErrorResponse
from novel_os.api.workflow_routes import router as workflow_router
from novel_os.core.config import Settings
from novel_os.core.logging import configure_logging
from novel_os.db.session import Database


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings.from_file()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(settings)
        app.state.database = database
        try:
            yield
        finally:
            database.dispose()

    app = FastAPI(
        title="Novel OS Backend",
        version="0.1.0",
        lifespan=lifespan,
        responses={status: {"model": ErrorResponse} for status in (403, 404, 405, 409, 422, 500)},
    )
    app.state.settings = settings
    app.add_middleware(RequestContextMiddleware)
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(core_router, prefix="/api/v1")
    app.include_router(workflow_router, prefix="/api/v1")
    app.include_router(agent_router, prefix="/api/v1")
    return app
