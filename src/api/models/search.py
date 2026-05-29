"""Search response models for API contracts."""
"""Pydantic models for the search API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchResult(BaseModel):
    """Represent one ranked accelerator returned by search."""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(description="Display title for the accelerator.")
    description: str = Field(
        default="",
        description="Short summary shown to the caller.",
    )
    score: float = Field(description="Ranking score for the result.")
    url: str = Field(description="Canonical URL for the accelerator.")


class SearchResponse(BaseModel):
    """Represent the public payload returned by the search endpoint."""


    query: str = Field(description="Normalized search text.")
    top: int = Field(ge=1, description="Maximum number of results returned.")
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Ranked accelerator search results.",
    """Represent a single ranked search result."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(description="Display title for the matched item.")
    description: str = Field(
        description="Short description chosen for the search result."
    )
    score: float = Field(
        description="Ranking score returned by Azure AI Search."
    )
    url: str = Field(description="Canonical URL for the matched item.")


    """Represent the response payload returned by the search endpoint."""


    query: str = Field(description="Normalized user query string.")
    top: int = Field(description="Maximum number of results requested.")
class SearchResponse(BaseModel):
    """Represent the response payload returned by the search endpoint."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(description="Normalized user query string.")
    top: int = Field(description="Maximum number of results requested.")
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Ranked search results.",
    )
