"""Pydantic models for FastAPI request and response contracts."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

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

__all__ = ["SearchResponse", "SearchResult"]
class UserProfile(BaseModel):
    """Represent the persisted user profile returned by /me."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="Document identifier in Cosmos DB.")
    user_id: str = Field(description="Stable application user identifier.")
    email: str | None = Field(
        default=None,
        description="Latest email address observed in user claims.",
    )
    name: str | None = Field(
        default=None,
        description="Latest display name observed in user claims.",
    )
    created_at: datetime = Field(
        description="Timestamp when the profile was first created.",
    )
    updated_at: datetime = Field(
        description="Timestamp when the profile was last updated.",
    )
    deleted_at: datetime | None = Field(
        default=None,
        description="Timestamp when GDPR deletion was requested.",
    )
    cleanup_pending: bool = Field(
        default=False,
        description="Whether background cleanup still needs to run.",
    )
    cleanup_requested_at: datetime | None = Field(
        default=None,
        description="Timestamp when cleanup was queued.",
    )
    deletion_scheduled_at: datetime | None = Field(
        default=None,
        description="Timestamp when background deletion was scheduled.",
    )


class ChatHistoryItem(BaseModel):
    """Represent one chat history item returned from Cosmos DB."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(description="History document identifier.")
    conversation_id: str | None = Field(
        default=None,
        description="Conversation identifier for grouped chat items.",
    )
    user_id: str = Field(description="User identifier that owns the row.")
    prompt: str | None = Field(
        default=None,
        description="Prompt content submitted by the user.",
    )
    response: str | None = Field(
        default=None,
        description="Assistant response stored for the conversation.",
    )
    created_at: datetime = Field(
        description="Timestamp when the history item was stored.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata associated with the chat item.",
    )


class ChatHistoryPage(BaseModel):
    """Represent a paginated chat history response."""

    items: list[ChatHistoryItem] = Field(
        default_factory=list,
        description="Chat history items for the requested page.",
    )
    limit: int = Field(description="Maximum items requested by the caller.")
    offset: int = Field(description="Zero-based starting index.")


class ExportData(BaseModel):
    """Represent the GDPR export payload for an authenticated user."""

    profile: UserProfile = Field(description="The exported user profile.")
    history: list[ChatHistoryItem] = Field(
        default_factory=list,
        description="All exported chat history items.",
    )
    exported_at: datetime = Field(
        description="Timestamp when the export was generated.",
    )


class DeletionResponse(BaseModel):
    """Represent the accepted GDPR account deletion response."""

    user_id: str = Field(description="User identifier scheduled for deletion.")
    deleted_at: datetime | None = Field(
        default=None,
        description="Timestamp when the deletion request was recorded.",
    )
    cleanup_pending: bool = Field(
        description="Whether background cleanup is still pending.",
    )
    deletion_scheduled_at: datetime | None = Field(
        default=None,
        description="Timestamp when background deletion was scheduled.",
    )


__all__ = [
    "ChatHistoryItem",
    "ChatHistoryPage",
    "DeletionResponse",
    "ExportData",
    "UserClaims",
    "UserProfile",
]
