"""User profile and GDPR helpers backed by Azure Cosmos DB."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

from azure.core.credentials import TokenCredential
from azure.cosmos import CosmosClient
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)
from azure.identity import DefaultAzureCredential

from src.api.config import Settings
from src.api.models import ChatHistoryItem, ExportData, UserClaims, UserProfile

LOGGER = logging.getLogger(__name__)
COSMOS_HOST_SUFFIX = ".documents.azure.com"


class ContainerProtocol(Protocol):
    """Define the Cosmos container surface needed by the service."""

    def read_item(self, *, item: str, partition_key: str) -> dict[str, Any]:
        """Read a single document from Cosmos DB."""

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        """Create or replace a document in Cosmos DB."""

    def query_items(
        self,
        *,
        query: str,
        parameters: list[dict[str, Any]],
        enable_cross_partition_query: bool,
    ) -> list[dict[str, Any]]:
        """Execute a Cosmos SQL query and return matching items."""


class UserServiceError(RuntimeError):
    """Raise when a Cosmos-backed user operation cannot complete."""


class UserServiceConfigurationError(UserServiceError):
    """Raise when the user service configuration is incomplete."""


def validate_cosmos_endpoint(value: str | None) -> str:
    """Validate the configured Cosmos DB endpoint before client use."""

    if value is None:
        raise UserServiceConfigurationError(
            "AZURE_COSMOS_ENDPOINT must be configured."
        )

    endpoint = value.strip()
    if not endpoint or endpoint.lower() == "none":
        raise UserServiceConfigurationError(
            "AZURE_COSMOS_ENDPOINT must be configured."
        )

    parsed_endpoint = urlparse(endpoint)
    hostname = parsed_endpoint.hostname
    if (
        parsed_endpoint.scheme != "https"
        or hostname is None
        or parsed_endpoint.username is not None
        or parsed_endpoint.password is not None
        or bool(parsed_endpoint.query)
        or bool(parsed_endpoint.fragment)
    ):
        raise UserServiceConfigurationError(
            "AZURE_COSMOS_ENDPOINT must be an https:// Azure endpoint."
        )

    if not hostname.lower().endswith(COSMOS_HOST_SUFFIX):
        raise UserServiceConfigurationError(
            "AZURE_COSMOS_ENDPOINT must match the Azure Cosmos DB "
            "host pattern *.documents.azure.com."
        )

    return endpoint.rstrip("/")


def _require_setting(value: str | None, *, env_var: str) -> str:
    """Return a required environment-backed value or raise an error."""

    if value is None:
        raise UserServiceConfigurationError(f"{env_var} must be configured.")

    normalized_value = value.strip()
    if not normalized_value:
        raise UserServiceConfigurationError(f"{env_var} must be configured.")

    return normalized_value


def _utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for persisted records."""

    return datetime.now(UTC)


class UserService:
    """Read and write user profile data stored in Azure Cosmos DB."""

    def __init__(
        self,
        *,
        settings: Settings | None = None,
        credential: TokenCredential | None = None,
        cosmos_client: CosmosClient | Any | None = None,
        user_container: ContainerProtocol | None = None,
        history_container: ContainerProtocol | None = None,
    ) -> None:
        """Create the service using managed identity by default."""

        self._settings = settings or Settings()
        self._credential = credential or DefaultAzureCredential()
        self._cosmos_client = cosmos_client

        if user_container is not None and history_container is not None:
            self._user_container = user_container
            self._history_container = history_container
            return

        endpoint = validate_cosmos_endpoint(
            self._settings.azure_cosmos_endpoint
        )
        database_name = _require_setting(
            self._settings.azure_cosmos_database,
            env_var="AZURE_COSMOS_DATABASE",
        )
        users_container_name = _require_setting(
            self._settings.azure_cosmos_container_users,
            env_var="AZURE_COSMOS_CONTAINER_USERS",
        )
        history_container_name = _require_setting(
            self._settings.azure_cosmos_container_history,
            env_var="AZURE_COSMOS_CONTAINER_HISTORY",
        )

        self._cosmos_client = cosmos_client or CosmosClient(
            endpoint,
            credential=self._credential,
        )
        database_client = self._cosmos_client.get_database_client(
            database_name
        )
        self._user_container = (
            user_container
            or database_client.get_container_client(users_container_name)
        )
        self._history_container = (
            history_container
            or database_client.get_container_client(history_container_name)
        )

    def get_or_create_profile(self, user: UserClaims) -> UserProfile:
        """Return the user profile, creating it on first authenticated use."""

        try:
            document = self._user_container.read_item(
                item=user.sub,
                partition_key=user.sub,
            )
        except CosmosResourceNotFoundError:
            LOGGER.info("Creating new profile for user %s", user.sub)
            return self._create_profile(user)
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to read profile for user %s", user.sub)
            raise UserServiceError("Failed to load the user profile.") from exc

        return self._sync_profile_document(document=document, user=user)

    def get_history(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[ChatHistoryItem]:
        """Return a page of chat history rows for the authenticated user."""

        query = (
            "SELECT * FROM c WHERE c.user_id = @user_id "
            "ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        )
        parameters = [
            {"name": "@user_id", "value": user_id},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        return self._query_history_items(query=query, parameters=parameters)

    def export_user_data(self, user: UserClaims) -> ExportData:
        """Aggregate the complete user profile and chat history export."""

        history = self._query_history_items(
            query=(
                "SELECT * FROM c WHERE c.user_id = @user_id "
                "ORDER BY c.created_at DESC"
            ),
            parameters=[{"name": "@user_id", "value": user.sub}],
        )
        return ExportData(
            profile=self.get_or_create_profile(user),
            history=history,
            exported_at=_utc_now(),
        )

    def soft_delete_user(self, user: UserClaims) -> UserProfile:
        """Soft-delete the user and mark the account for cleanup."""

        profile = self.get_or_create_profile(user)
        deleted_at = _utc_now()
        document = profile.model_dump(mode="json")
        document.update(
            {
                "deleted_at": deleted_at.isoformat(),
                "cleanup_pending": True,
                "cleanup_requested_at": deleted_at.isoformat(),
                "updated_at": deleted_at.isoformat(),
            }
        )

        try:
            self._user_container.upsert_item(body=document)
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to soft-delete user %s", user.sub)
            raise UserServiceError(
                "Failed to delete the user profile."
            ) from exc

        return UserProfile.model_validate(document)

    def _create_profile(self, user: UserClaims) -> UserProfile:
        """Create a new user profile document in Cosmos DB."""

        timestamp = _utc_now()
        profile = UserProfile(
            id=user.sub,
            user_id=user.sub,
            email=user.email,
            name=user.name,
            created_at=timestamp,
            updated_at=timestamp,
        )

        try:
            self._user_container.upsert_item(body=profile.model_dump(mode="json"))
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to create profile for user %s", user.sub)
            raise UserServiceError(
                "Failed to create the user profile."
            ) from exc

        return profile

    def _sync_profile_document(
        self,
        *,
        document: dict[str, Any],
        user: UserClaims,
    ) -> UserProfile:
        """Keep mutable profile fields aligned with the latest token claims."""

        updated_document = dict(document)
        changed = False
        if updated_document.get("email") != user.email:
            updated_document["email"] = user.email
            changed = True
        if updated_document.get("name") != user.name:
            updated_document["name"] = user.name
            changed = True
        if updated_document.get("user_id") != user.sub:
            updated_document["user_id"] = user.sub
            changed = True
        if updated_document.get("id") != user.sub:
            updated_document["id"] = user.sub
            changed = True

        if changed:
            updated_document["updated_at"] = _utc_now().isoformat()
            try:
                self._user_container.upsert_item(body=updated_document)
            except CosmosHttpResponseError as exc:
                LOGGER.exception(
                    "Failed to update profile for user %s",
                    user.sub,
                )
                raise UserServiceError(
                    "Failed to update the user profile."
                ) from exc

        return UserProfile.model_validate(updated_document)

    def _query_history_items(
        self,
        *,
        query: str,
        parameters: list[dict[str, Any]],
    ) -> list[ChatHistoryItem]:
        """Run a history query and convert raw rows into typed models."""

        try:
            items = list(
                self._history_container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                )
            )
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to query user history.")
            raise UserServiceError("Failed to load user history.") from exc

        return [ChatHistoryItem.model_validate(item) for item in items]
