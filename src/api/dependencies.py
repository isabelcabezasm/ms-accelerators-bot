"""Dependency helpers for the FastAPI application."""

from src.api.config import Settings, get_settings


def get_app_settings() -> Settings:
    """Expose settings through a dedicated dependency function."""

    return get_settings()
