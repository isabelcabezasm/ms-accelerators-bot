"""Dependency helpers for the FastAPI application."""

from functools import lru_cache

from src.api.config import Settings, get_settings
from src.api.search_service import SearchService


def get_app_settings() -> Settings:
    """Expose settings through a dedicated dependency function."""

    return get_settings()


@lru_cache
def get_search_service() -> SearchService:
    """Build the search service dependency for request handlers."""
    """Create and cache the Azure-backed search service dependency."""

    return SearchService()
