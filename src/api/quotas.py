"""Cosmos-backed daily quota enforcement for chat requests."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from typing import Any

from azure.core import MatchConditions
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential
from fastapi import HTTPException, status
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.ingestion.search_client import validate_azure_endpoint

LOGGER = logging.getLogger(__name__)
COSMOS_HOST_SUFFIX = ".documents.azure.com"
COSMOS_ITEM_TTL_SECONDS = 48 * 60 * 60
_MAX_WRITE_ATTEMPTS = 3


class QuotaSettings(BaseSettings):
    """Load the Cosmos DB-backed chat quota settings."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    cosmos_endpoint: str | None = Field(
        default=None,
        alias="AZURE_COSMOS_ENDPOINT",
    )
    cosmos_database: str = Field(
        alias="AZURE_COSMOS_DATABASE",
        min_length=1,
    )
    cosmos_container_quotas: str = Field(
        alias="AZURE_COSMOS_CONTAINER_QUOTAS",
        min_length=1,
    )
    daily_chat_quota: int = Field(
        default=50,
        alias="DAILY_CHAT_QUOTA",
        ge=1,
    )

    @field_validator("cosmos_endpoint")
    @classmethod
    def validate_cosmos_endpoint(cls, value: str | None) -> str:
        """Require a valid Azure Cosmos DB endpoint URL."""

        return validate_azure_endpoint(
            value,
            env_var="AZURE_COSMOS_ENDPOINT",
            host_suffix=COSMOS_HOST_SUFFIX,
        )


class QuotaExceededError(HTTPException):
    """Represent a daily quota violation with retry metadata."""

    def __init__(self, *, retry_after: int) -> None:
        """Build the quota exceeded response returned to callers."""

        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Daily chat quota exceeded.",
            headers={"Retry-After": str(retry_after)},
        )
        self.retry_after = retry_after


class QuotaService:
    """Track per-user daily chat usage in Azure Cosmos DB."""

    def __init__(
        self,
        *,
        settings: QuotaSettings | None = None,
        credential: Any | None = None,
        cosmos_client: CosmosClient | Any | None = None,
        container_client: Any | None = None,
        now_provider: Callable[[], datetime] | None = None,
    ) -> None:
        """Create the quota service using managed identity by default."""

        self._settings = settings or QuotaSettings()
        self._credential = credential
        self._cosmos_client = cosmos_client
        self._container_client = container_client
        self._now_provider = now_provider or self._utc_now

    def check_and_increment(self, user_id: str) -> dict[str, Any]:
        """Consume one chat quota unit for the given user."""

        normalized_user_id = user_id.strip()
        if not normalized_user_id:
            raise ValueError("user_id must not be empty.")

        now = self._get_current_time()
        quota_date = now.date().isoformat()
        retry_after = self._seconds_until_reset(now)
        item_id = self._build_item_id(normalized_user_id, quota_date)
        container_client = self._get_container_client()

        for attempt in range(_MAX_WRITE_ATTEMPTS):
            document = self._read_document(
                container_client,
                item_id=item_id,
                user_id=normalized_user_id,
            )
            if document is None:
                new_document = self._build_document(
                    user_id=normalized_user_id,
                    quota_date=quota_date,
                    count=1,
                )
                try:
                    container_client.create_item(body=new_document)
                except CosmosHttpResponseError as error:
                    if (
                        getattr(error, "status_code", None) == 409
                        and attempt < _MAX_WRITE_ATTEMPTS - 1
                    ):
                        continue
                    self._raise_service_unavailable(error)
                return new_document

            current_count = self._read_count(document)
            if current_count >= self._settings.daily_chat_quota:
                LOGGER.info(
                    "Daily chat quota exceeded",
                    extra={
                        "user_id": normalized_user_id,
                        "quota_date": quota_date,
                        "limit": self._settings.daily_chat_quota,
                    },
                )
                raise QuotaExceededError(retry_after=retry_after)

            updated_document = self._build_document(
                user_id=normalized_user_id,
                quota_date=quota_date,
                count=current_count + 1,
            )
            try:
                self._replace_document(
                    container_client,
                    item_id=item_id,
                    current_document=document,
                    updated_document=updated_document,
                )
            except CosmosHttpResponseError as error:
                if (
                    getattr(error, "status_code", None) == 412
                    and attempt < _MAX_WRITE_ATTEMPTS - 1
                ):
                    continue
                self._raise_service_unavailable(error)
            return updated_document

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quota service is unavailable.",
        )

    def _get_container_client(self) -> Any:
        """Create the Cosmos container client lazily for testability."""

        if self._container_client is not None:
            return self._container_client

        if self._credential is None:
            self._credential = DefaultAzureCredential()

        if self._cosmos_client is None:
            self._cosmos_client = CosmosClient(
                url=self._settings.cosmos_endpoint,
                credential=self._credential,
            )

        database_client = self._cosmos_client.get_database_client(
            self._settings.cosmos_database,
        )
        self._container_client = database_client.get_container_client(
            self._settings.cosmos_container_quotas,
        )
        return self._container_client

    def _read_document(
        self,
        container_client: Any,
        *,
        item_id: str,
        user_id: str,
    ) -> Mapping[str, Any] | None:
        """Read the current user's daily counter document when present."""

        try:
            return container_client.read_item(
                item=item_id,
                partition_key=user_id,
            )
        except CosmosResourceNotFoundError:
            return None
        except CosmosHttpResponseError as error:
            self._raise_service_unavailable(error)

    def _replace_document(
        self,
        container_client: Any,
        *,
        item_id: str,
        current_document: Mapping[str, Any],
        updated_document: dict[str, Any],
    ) -> None:
        """Replace an existing counter document using optimistic locking."""

        replace_kwargs: dict[str, Any] = {
            "item": item_id,
            "body": updated_document,
        }
        etag = current_document.get("_etag")
        if isinstance(etag, str) and etag:
            replace_kwargs["etag"] = etag
            replace_kwargs["match_condition"] = (
                MatchConditions.IfNotModified
            )
        container_client.replace_item(**replace_kwargs)

    def _read_count(self, document: Mapping[str, Any]) -> int:
        """Normalize the current quota count stored in Cosmos DB."""

        count = document.get("count", 0)
        if isinstance(count, int) and count >= 0:
            return count

        LOGGER.warning(
            "Resetting invalid quota counter",
            extra={"count": count},
        )
        return 0

    def _build_document(
        self,
        *,
        user_id: str,
        quota_date: str,
        count: int,
    ) -> dict[str, Any]:
        """Build the persisted Cosmos document for a daily counter."""

        return {
            "id": self._build_item_id(user_id, quota_date),
            "user_id": user_id,
            "date": quota_date,
            "count": count,
            "ttl": COSMOS_ITEM_TTL_SECONDS,
        }

    def _build_item_id(self, user_id: str, quota_date: str) -> str:
        """Build the stable Cosmos item identifier for a daily counter."""

        return f"{user_id}:{quota_date}"

    def _get_current_time(self) -> datetime:
        """Return the current time normalized to UTC."""

        current_time = self._now_provider()
        if current_time.tzinfo is None:
            return current_time.replace(tzinfo=UTC)
        return current_time.astimezone(UTC)

    def _seconds_until_reset(self, current_time: datetime) -> int:
        """Calculate the retry delay until the next UTC day begins."""

        next_day = datetime(
            current_time.year,
            current_time.month,
            current_time.day,
            tzinfo=UTC,
        ) + timedelta(days=1)
        remaining_seconds = int((next_day - current_time).total_seconds())
        return max(1, remaining_seconds)

    def _raise_service_unavailable(
        self,
        error: CosmosHttpResponseError,
    ) -> None:
        """Log Cosmos errors and return a consistent API failure."""

        LOGGER.exception("Cosmos quota request failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Quota service is unavailable.",
        ) from error

    @staticmethod
    def _utc_now() -> datetime:
        """Return the current UTC timestamp."""

        return datetime.now(UTC)
