"""Shared Pydantic models used across backend services."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Represent a liveness response from the API."""

    status: str = Field(
        default="ok",
        description="Current health status for the API.",
    )
