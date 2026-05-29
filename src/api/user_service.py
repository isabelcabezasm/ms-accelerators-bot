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
DELETION_MARKER_PREFIX = "deletion-marker:"
DELETION_MARKER_TYPE = "deletion_marker"


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
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Execute a Cosmos SQL query and return matching items."""


class UserServiceError(RuntimeError):
    """Raise when a Cosmos-backed user operation cannot complete."""


class UserServiceConfigurationError(UserServiceError):
    """Raise when the user service configuration is incomplete."""


class UserDeletionPendingError(UserServiceError):
    """Raise when the authenticated account is awaiting deletion."""


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


def _marker_id(user_id: str) -> str:
    """Build the deletion marker identifier for a user."""

    return f"{DELETION_MARKER_PREFIX}{user_id}"


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
        quota_container: ContainerProtocol | None = None,
    ) -> None:
        """Create the service using managed identity by default."""

        self._settings = settings or Settings()
        self._credential = credential or DefaultAzureCredential()
        self._cosmos_client = cosmos_client

        if (
            user_container is not None
            and history_container is not None
            and quota_container is not None
        ):
            self._user_container = user_container
            self._history_container = history_container
            self._quota_container = quota_container
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
        quota_container_name = _require_setting(
            self._settings.azure_cosmos_container_quotas,
            env_var="AZURE_COSMOS_CONTAINER_QUOTAS",
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
        self._quota_container = (
            quota_container
            or database_client.get_container_client(quota_container_name)
        )

    def get_or_create_profile(self, user: UserClaims) -> UserProfile:
        """Return the user profile, creating it on first authenticated use."""

        deletion_marker = self._get_deletion_marker(user.sub)
        document = self._read_profile_document(user.sub)
        if document is None:
            if deletion_marker is not None:
                raise UserDeletionPendingError(
                    "Account deletion is pending."
                )
            LOGGER.info("Creating new profile for user %s", user.sub)
            return self._create_profile(user)

        validated_document = self._validate_profile_document(
            document=document,
            user_id=user.sub,
        )
        if (
            deletion_marker is not None
            or self._profile_deletion_pending(validated_document)
        ):
            return UserProfile.model_validate(validated_document)

        return self._sync_profile_document(
            document=validated_document,
            user=user,
        )

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
            "AND (NOT IS_DEFINED(c.document_type) "
            "OR c.document_type != @deletion_marker_type) "
            "ORDER BY c.created_at DESC OFFSET @offset LIMIT @limit"
        )
        parameters = [
            {"name": "@user_id", "value": user_id},
            {
                "name": "@deletion_marker_type",
                "value": DELETION_MARKER_TYPE,
            },
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": limit},
        ]
        return self._query_history_items(
            query=query,
            parameters=parameters,
            user_id=user_id,
        )

    def export_user_data(self, user: UserClaims) -> ExportData:
        """Aggregate the complete user profile and chat history export."""

        history = self._query_history_items(
            query=(
                "SELECT * FROM c WHERE c.user_id = @user_id "
                "AND (NOT IS_DEFINED(c.document_type) "
                "OR c.document_type != @deletion_marker_type) "
                "ORDER BY c.created_at DESC"
            ),
            parameters=[
                {"name": "@user_id", "value": user.sub},
                {
                    "name": "@deletion_marker_type",
                    "value": DELETION_MARKER_TYPE,
                },
            ],
            user_id=user.sub,
        )
        return ExportData(
            profile=self.get_or_create_profile(user),
            history=history,
            exported_at=_utc_now(),
        )

    def soft_delete_user(self, user: UserClaims) -> UserProfile:
        """Soft-delete the user and mark the account for cleanup."""

        deletion_marker = self._get_deletion_marker(user.sub)
        profile_document = self._read_profile_document(user.sub)
        if deletion_marker is not None and profile_document is None:
            return self._profile_from_deletion_marker(
                user=user,
                marker=deletion_marker,
            )

        if profile_document is None:
            profile = self._create_profile(user)
            profile_document = profile.model_dump(mode="json")
        else:
            profile_document = self._validate_profile_document(
                document=profile_document,
                user_id=user.sub,
            )

        deleted_at = _utc_now()
        if self._profile_deletion_pending(profile_document):
            deleted_at = self._coerce_datetime(
                profile_document.get("deletion_scheduled_at")
                or profile_document.get("deleted_at"),
                fallback=deleted_at,
            )

        profile_document.update(
            {
                "deleted_at": deleted_at.isoformat(),
                "cleanup_pending": True,
                "cleanup_requested_at": deleted_at.isoformat(),
                "deletion_scheduled_at": deleted_at.isoformat(),
                "updated_at": deleted_at.isoformat(),
            }
        )
        profile = UserProfile.model_validate(profile_document)

        try:
            self._user_container.upsert_item(body=profile_document)
            self._upsert_deletion_markers(
                profile=profile,
                deleted_at=deleted_at,
            )
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to soft-delete user %s", user.sub)
            raise UserServiceError(
                "Failed to delete the user profile."
            ) from exc

        return profile

    def _create_profile(self, user: UserClaims) -> UserProfile:
        """Create a new user profile document in Cosmos DB."""

        if self._get_deletion_marker(user.sub) is not None:
            raise UserDeletionPendingError("Account deletion is pending.")

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

        if self._profile_deletion_pending(document):
            return UserProfile.model_validate(document)

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
        user_id: str,
    ) -> list[ChatHistoryItem]:
        """Run a history query and convert raw rows into typed models."""

        try:
            items = list(
                self._history_container.query_items(
                    query=query,
                    parameters=parameters,
                    enable_cross_partition_query=True,
                    partition_key=user_id,
                )
            )
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to query user history.")
            raise UserServiceError("Failed to load user history.") from exc

        history_items: list[ChatHistoryItem] = []
        for item in items:
            if item.get("user_id") != user_id:
                raise UserServiceError(
                    "Unauthorized history item returned for the user."
                )
            history_items.append(ChatHistoryItem.model_validate(item))

        return history_items

    def _read_profile_document(self, user_id: str) -> dict[str, Any] | None:
        """Read the persisted profile document for a specific user."""

        try:
            return self._user_container.read_item(
                item=user_id,
                partition_key=user_id,
            )
        except CosmosResourceNotFoundError:
            return None
        except CosmosHttpResponseError as exc:
            LOGGER.exception("Failed to read profile for user %s", user_id)
            raise UserServiceError("Failed to load the user profile.") from exc

    def _get_deletion_marker(self, user_id: str) -> dict[str, Any] | None:
        """Return the persisted deletion marker when cleanup is pending."""

        try:
            marker = self._user_container.read_item(
                item=_marker_id(user_id),
                partition_key=user_id,
            )
        except CosmosResourceNotFoundError:
            return None
        except CosmosHttpResponseError as exc:
            LOGGER.exception(
                "Failed to read deletion marker for user %s",
                user_id,
            )
            raise UserServiceError(
                "Failed to load the user deletion state."
            ) from exc

        if marker.get("user_id") != user_id:
            raise UserServiceError(
                "Unauthorized deletion marker returned for the user."
            )

        return marker

    def _validate_profile_document(
        self,
        *,
        document: dict[str, Any],
        user_id: str,
    ) -> dict[str, Any]:
        """Validate that the loaded profile belongs to the caller."""

        validated_document = dict(document)
        document_id = validated_document.get("id")
        document_user_id = validated_document.get("user_id")
        if document_id != user_id:
            raise UserServiceError(
                "Unauthorized profile document returned for the user."
            )
        if document_user_id not in (None, user_id):
            raise UserServiceError(
                "Unauthorized profile document returned for the user."
            )
        validated_document.setdefault("user_id", user_id)
        return validated_document

    def _profile_deletion_pending(self, document: dict[str, Any]) -> bool:
        """Return whether a profile document is already pending deletion."""

        return bool(
            document.get("cleanup_pending")
            or document.get("deleted_at")
            or document.get("deletion_scheduled_at")
        )

    def _upsert_deletion_markers(
        self,
        *,
        profile: UserProfile,
        deleted_at: datetime,
    ) -> None:
        """Persist cleanup markers in every user-owned Cosmos container."""

        container_map = (
            ("profile", self._user_container),
            ("history", self._history_container),
            ("quotas", self._quota_container),
        )
        for target_container, container in container_map:
            container.upsert_item(
                body=self._build_deletion_marker(
                    profile=profile,
                    deleted_at=deleted_at,
                    target_container=target_container,
                )
            )

    def _build_deletion_marker(
        self,
        *,
        profile: UserProfile,
        deleted_at: datetime,
        target_container: str,
    ) -> dict[str, Any]:
        """Create the deletion marker stored for background cleanup."""

        return {
            "id": _marker_id(profile.user_id),
            "user_id": profile.user_id,
            "document_type": DELETION_MARKER_TYPE,
            "target_container": target_container,
            "email": profile.email,
            "name": profile.name,
            "created_at": profile.created_at.isoformat(),
            "updated_at": deleted_at.isoformat(),
            "deleted_at": deleted_at.isoformat(),
            "cleanup_pending": True,
            "cleanup_requested_at": deleted_at.isoformat(),
            "deletion_scheduled_at": deleted_at.isoformat(),
        }

    def _profile_from_deletion_marker(
        self,
        *,
        user: UserClaims,
        marker: dict[str, Any],
    ) -> UserProfile:
        """Rebuild a pending-deletion profile from its marker document."""

        deleted_at = self._coerce_datetime(
            marker.get("deleted_at"),
            fallback=_utc_now(),
        )
        return UserProfile.model_validate(
            {
                "id": user.sub,
                "user_id": user.sub,
                "email": marker.get("email", user.email),
                "name": marker.get("name", user.name),
                "created_at": marker.get("created_at", deleted_at.isoformat()),
                "updated_at": marker.get("updated_at", deleted_at.isoformat()),
                "deleted_at": deleted_at.isoformat(),
                "cleanup_pending": True,
                "cleanup_requested_at": marker.get(
                    "cleanup_requested_at",
                    deleted_at.isoformat(),
                ),
                "deletion_scheduled_at": marker.get(
                    "deletion_scheduled_at",
                    deleted_at.isoformat(),
                ),
            }
        )

    def _coerce_datetime(
        self,
        value: Any,
        *,
        fallback: datetime,
    ) -> datetime:
        """Convert stored timestamps into timezone-aware datetime values."""

        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return fallback
        return fallback
