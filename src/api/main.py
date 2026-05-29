"""FastAPI application entry point."""

from fastapi import FastAPI

from src.api.config import get_settings
from src.shared.models import HealthResponse


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )

    @app.get("/healthz", response_model=HealthResponse, tags=["health"])
    def healthz() -> HealthResponse:
        """Return a basic health response for liveness checks."""

        return HealthResponse(status="ok")

    return app


app = create_app()
