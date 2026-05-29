"""FastAPI dependency for enforcing daily chat quotas."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from src.api.auth import get_current_user
from src.api.dependencies import get_quota_service
from src.api.models import UserClaims
from src.api.quotas import QuotaService


async def enforce_daily_chat_quota(
    user: Annotated[UserClaims, Depends(get_current_user)],
    quota_service: Annotated[QuotaService, Depends(get_quota_service)],
) -> None:
    """Consume one daily chat quota unit before handling /chat."""

    quota_service.check_and_increment(user.sub)
