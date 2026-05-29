"""Search response models for API contracts."""

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

    model_config = ConfigDict(extra="ignore")

    query: str = Field(description="Normalized search text.")
    top: int = Field(ge=1, description="Maximum number of results returned.")
    results: list[SearchResult] = Field(
        default_factory=list,
        description="Ranked accelerator search results.",
    )
