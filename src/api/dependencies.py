"""Dependency helpers for the FastAPI application."""

from functools import lru_cache

from src.api.config import Settings, get_settings
from src.api.search_service import SearchService
from __future__ import annotations

import logging

from fastapi import HTTPException, status

from src.api.config import Settings, get_settings
from src.api.user_service import UserService, UserServiceConfigurationError

LOGGER = logging.getLogger(__name__)
from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from src.api.config import Settings, get_settings
from src.api.quotas import QuotaService

if TYPE_CHECKING:
    from src.api.search_service import SearchService


def get_app_settings() -> Settings:
    """Expose settings through a dedicated dependency function."""

    return get_settings()


@lru_cache
def get_search_service() -> SearchService:
    """Build the search service dependency for request handlers."""
    """Create and cache the Azure-backed search service dependency."""

    return SearchService()
def get_user_service() -> UserService:
    """Build the user service or surface configuration failures clearly."""

    try:
        return UserService(settings=get_app_settings())
    except UserServiceConfigurationError as exc:
        LOGGER.exception("User service configuration is incomplete.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="User storage is not configured.",
        ) from exc
    """Create and cache the Azure-backed search service dependency."""

    from src.api.search_service import SearchService

    return SearchService()


@lru_cache
def get_quota_service() -> QuotaService:
    """Create and cache the Cosmos-backed quota service dependency."""

    return QuotaService()
