"""Authenticated /me endpoints for profile, history, and GDPR flows."""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.auth import get_current_user
from src.api.dependencies import get_user_service
from src.api.models import (
    ChatHistoryPage,
    DeletionResponse,
    ExportData,
    UserClaims,
    UserProfile,
)
from src.api.user_service import UserService, UserServiceError

LOGGER = logging.getLogger(__name__)
router = APIRouter(prefix="/me", tags=["me"])


def _raise_user_service_error(
    *,
    operation: str,
    user_id: str,
    exc: UserServiceError,
) -> None:
    """Translate service errors into consistent API error responses."""

    LOGGER.exception(
        "Failed to %s for user %s",
        operation,
        user_id,
        exc_info=exc,
    )
    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail=f"Unable to {operation}.",
    ) from exc


@router.get("", response_model=UserProfile)
async def get_me(
    current_user: Annotated[UserClaims, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> UserProfile:
    """Return the caller profile, creating it when missing."""

    try:
        return user_service.get_or_create_profile(current_user)
    except UserServiceError as exc:
        _raise_user_service_error(
            operation="load the user profile",
            user_id=current_user.sub,
            exc=exc,
        )


@router.get("/history", response_model=ChatHistoryPage)
async def get_me_history(
    current_user: Annotated[UserClaims, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ChatHistoryPage:
    """Return a paginated slice of the caller chat history."""

    try:
        history = user_service.get_history(
            current_user.sub,
            limit=limit,
            offset=offset,
        )
    except UserServiceError as exc:
        _raise_user_service_error(
            operation="load chat history",
            user_id=current_user.sub,
            exc=exc,
        )

    return ChatHistoryPage(items=history, limit=limit, offset=offset)


@router.get("/export", response_model=ExportData)
async def export_me(
    current_user: Annotated[UserClaims, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> ExportData:
    """Export the caller profile and chat history as GDPR JSON data."""

    try:
        return user_service.export_user_data(current_user)
    except UserServiceError as exc:
        _raise_user_service_error(
            operation="export user data",
            user_id=current_user.sub,
            exc=exc,
        )


@router.delete(
    "",
    response_model=DeletionResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def delete_me(
    current_user: Annotated[UserClaims, Depends(get_current_user)],
    user_service: Annotated[UserService, Depends(get_user_service)],
) -> DeletionResponse:
    """Soft-delete the caller profile and queue background cleanup."""

    try:
        profile = user_service.soft_delete_user(current_user)
    except UserServiceError as exc:
        _raise_user_service_error(
            operation="delete the user profile",
            user_id=current_user.sub,
            exc=exc,
        )

    return DeletionResponse(
        user_id=profile.user_id,
        deleted_at=profile.deleted_at,
        cleanup_pending=profile.cleanup_pending,
    )
