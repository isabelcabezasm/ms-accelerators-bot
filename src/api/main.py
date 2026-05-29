"""FastAPI application entry point."""

from fastapi import FastAPI

from src.api.config import get_settings
from src.api.routers.search import router as search_router
from src.api.middleware import TracingMiddleware
from src.api.telemetry import configure_telemetry
from src.api.routes.me import router as me_router
from src.shared.models import HealthResponse


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    settings = get_settings()
    telemetry = configure_telemetry(
        settings.app_name,
        settings.applicationinsights_connection_string,
    )
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )
    app.include_router(search_router)
    app.state.telemetry = telemetry
    app.add_middleware(TracingMiddleware, telemetry=telemetry)

    @app.get("/healthz", response_model=HealthResponse, tags=["health"])
    def healthz() -> HealthResponse:
        """Return a basic health response for liveness checks."""

        return HealthResponse(status="ok")

    app.include_router(me_router)
    return app


app = create_app()
