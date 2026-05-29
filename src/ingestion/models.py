"""Pydantic models for the accelerators.ms ingestion pipeline."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AcceleratorMetadata(BaseModel):
    """Represent normalized accelerator metadata from accelerators.ms."""

    name: str = Field(description="Human-readable accelerator name.")
    url: str = Field(description="Canonical accelerator repository URL.")
    summary: str = Field(description="Short accelerator summary.")
    categories: list[str] = Field(
        default_factory=list,
        description="Normalized categories derived from source taxonomy.",
    )
    industries: list[str] = Field(
        default_factory=list,
        description="Industries listed by accelerators.ms.",
    )
    azure_services: list[str] = Field(
        default_factory=list,
        description="Azure and Microsoft services used by the accelerator.",
    )
    languages: list[str] = Field(
        default_factory=list,
        description="Programming languages listed by accelerators.ms.",
    )
    deployment: str | None = Field(
        default=None,
        description="Derived deployment model for the accelerator.",
    )


class CrawlResult(BaseModel):
    """Represent one crawler execution against accelerators.ms."""

    source_url: str = Field(description="Catalog page URL that was crawled.")
    bundle_url: str | None = Field(
        default=None,
        description="JavaScript bundle URL used for structured parsing.",
    )
    accelerators: list[AcceleratorMetadata] = Field(
        default_factory=list,
        description="Structured accelerator metadata rows.",
    )
