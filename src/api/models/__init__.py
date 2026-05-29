"""Pydantic models for FastAPI request and response contracts."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.api.models.search import SearchResponse, SearchResult


class UserClaims(BaseModel):
    """Represent the authenticated user claims exposed to handlers."""

    model_config = ConfigDict(extra="ignore")

    sub: str = Field(description="Stable subject identifier from the token.")
    email: str | None = Field(
        default=None,
        description="Primary email-style identifier for the user.",
    )
    name: str | None = Field(
        default=None,
        description="Display name included in the access token.",
    )


__all__ = ["SearchResponse", "SearchResult", "UserClaims"]
from src.api.models.search import SearchResponse, SearchResult

__all__ = ["SearchResponse", "SearchResult"]
