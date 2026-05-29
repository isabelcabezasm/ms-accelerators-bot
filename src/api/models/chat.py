"""Pydantic models for the chat API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Citation(BaseModel):
    """Represents a source citation returned with a chat answer."""

    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., ge=1, description="Stable citation identifier.")
    accelerator_id: str = Field(..., min_length=1)
    accelerator_name: str = Field(..., min_length=1)
    chunk_id: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
    excerpt: str = Field(..., min_length=1)


class ChatRequest(BaseModel):
    """Validates incoming chat requests."""

    model_config = ConfigDict(extra="forbid")

    message: str = Field(..., min_length=1, description="User message.")
    conversation_id: str | None = Field(
        default=None,
        description="Optional conversation identifier to continue a thread.",
    )

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        """Reject empty or whitespace-only messages."""

        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("message must not be empty.")
        return cleaned_value


class ChatResponse(BaseModel):
    """Represents the response payload for the chat endpoint."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(..., min_length=1)
    citations: list[Citation] = Field(default_factory=list)
    conversation_id: str = Field(..., min_length=1)
