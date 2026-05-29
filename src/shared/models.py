"""Shared Pydantic models used across backend services."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class HealthResponse(BaseModel):
    """Represent a liveness response from the API."""

    status: str = Field(
        default="ok",
        description="Current health status for the API.",
    )


class AcceleratorDocument(BaseModel):
    """Represent a normalized accelerator document before chunking."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Stable accelerator identifier.")
    name: str = Field(description="Accelerator display name.")
    url: str = Field(description="Catalog URL for the accelerator.")
    github_url: str | None = Field(
        default=None,
        description="Optional GitHub repository URL.",
    )
    summary: str = Field(
        default="",
        description="Short marketing summary from the catalog.",
    )
    long_description: str = Field(
        default="",
        description="Normalized long-form README content.",
    )
    categories: list[str] = Field(
        default_factory=list,
        description="Scenario categories used for filtering.",
    )
    industries: list[str] = Field(
        default_factory=list,
        description="Industry tags used for filtering.",
    )
    azure_services: list[str] = Field(
        default_factory=list,
        description="Azure services referenced by the accelerator.",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages used by the accelerator.",
    )
    deployment: list[str] = Field(
        default_factory=list,
        description="Deployment technologies referenced by the accelerator.",
    )
    last_updated: date | datetime | None = Field(
        default=None,
        description="Last published update from the source metadata.",
    )
    stars: int = Field(
        default=0,
        ge=0,
        description="GitHub stargazer count.",
    )
    content_hash: str = Field(
        default="",
        description="Stable hash used to detect content changes.",
    )


class AcceleratorChunk(BaseModel):
    """Represent a searchable chunk derived from an accelerator."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str = Field(description="Deterministic chunk identifier.")
    parent_id: str = Field(description="Owning accelerator identifier.")
    chunk_index: int = Field(
        ge=0,
        description="Zero-based chunk position within the source document.",
    )
    name: str = Field(description="Accelerator display name.")
    summary: str = Field(
        default="",
        description="Short accelerator summary.",
    )
    content: str = Field(description="Chunk content used for retrieval.")
    url: str = Field(description="Catalog URL for the accelerator.")
    github_url: str | None = Field(
        default=None,
        description="Optional GitHub repository URL.",
    )
    categories: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    azure_services: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    deployment: list[str] = Field(default_factory=list)
    last_updated: date | datetime | None = Field(default=None)
    stars: int = Field(default=0, ge=0)
    content_hash: str = Field(
        default="",
        description="Parent document hash for idempotent upserts.",
    )
    content_vector: list[float] = Field(
        default_factory=list,
        description="Azure OpenAI embedding for the chunk content.",
    )

    def to_search_document(self) -> dict[str, Any]:
        """Convert the chunk into the Azure AI Search payload."""

        return {
            "id": self.chunk_id,
            "chunk_id": self.chunk_id,
            "parent_id": self.parent_id,
            "name": self.name,
            "summary": self.summary,
            "long_description": self.content,
            "url": self.url,
            "github_url": self.github_url,
            "categories": self.categories,
            "industries": self.industries,
            "azure_services": self.azure_services,
            "languages": self.languages,
            "deployment": self.deployment,
            "last_updated": self.last_updated,
            "stars": self.stars,
            "content_hash": self.content_hash,
            "content_vector": self.content_vector,
        }
