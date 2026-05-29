"""Tests for authenticated /me API endpoints and user service logic."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi.testclient import TestClient
from src.api.auth import get_current_user
from src.api.dependencies import get_user_service
from src.api.main import create_app
from src.api.models import (
    ChatHistoryItem,
    ExportData,
    UserClaims,
    UserProfile,
)
from src.api.user_service import (
    UserDeletionPendingError,
    UserService,
    UserServiceError,
)


class FakeUserService:
    """In-memory user service double used by the /me endpoint tests."""

    def __init__(
        self,
        *,
        profile: UserProfile | None = None,
        history: list[ChatHistoryItem] | None = None,
    ) -> None:
        """Seed the fake service with optional profile and history data."""

        self.profile = profile
        self.history = history or []
        self.deleted_containers: set[str] = set()

    def get_or_create_profile(self, user: UserClaims) -> UserProfile:
        """Return the stored profile or create one when it is missing."""

        if self.profile is None:
            timestamp = datetime.now(UTC)
            self.profile = UserProfile(
                id=user.sub,
                user_id=user.sub,
                email=user.email,
                name=user.name,
                created_at=timestamp,
                updated_at=timestamp,
            )

        if self.profile.cleanup_pending:
            raise UserDeletionPendingError("Account deletion is pending.")

        return self.profile

    def get_history(
        self,
        user_id: str,
        *,
        limit: int,
        offset: int,
    ) -> list[ChatHistoryItem]:
        """Return a paginated slice of the stored history items."""

        assert user_id == TEST_USER.sub
        return self.history[offset : offset + limit]

    def export_user_data(self, user: UserClaims) -> ExportData:
        """Return a full export payload for the authenticated user."""

        return ExportData(
            profile=self.get_or_create_profile(user),
            history=self.history,
            exported_at=datetime.now(UTC),
        )

    def soft_delete_user(self, user: UserClaims) -> UserProfile:
        """Mark the profile as deleted and pending cleanup."""

        profile = self.get_or_create_profile(user)
        deleted_at = datetime.now(UTC)
        self.deleted_containers = {"profile", "history", "quotas"}
        self.profile = profile.model_copy(
            update={
                "deleted_at": deleted_at,
                "cleanup_pending": True,
                "cleanup_requested_at": deleted_at,
                "deletion_scheduled_at": deleted_at,
                "updated_at": deleted_at,
            }
        )
        return self.profile


class FakeContainer:
    """Store Cosmos documents in memory for service-level tests."""

    def __init__(
        self,
        *,
        items: dict[str, dict[str, Any]] | None = None,
        query_results: list[dict[str, Any]] | None = None,
    ) -> None:
        """Seed the fake container with items and query results."""

        self.items = items or {}
        self.query_results = query_results or []
        self.upserts: list[dict[str, Any]] = []
        self.last_query: dict[str, Any] | None = None

    def read_item(self, *, item: str, partition_key: str) -> dict[str, Any]:
        """Return a stored item when the partition matches the user."""

        document = self.items.get(item)
        if document is None or document.get("user_id") != partition_key:
            raise CosmosResourceNotFoundError(
                status_code=404,
                message="Document not found.",
            )
        return dict(document)

    def upsert_item(self, body: dict[str, Any]) -> dict[str, Any]:
        """Persist the provided document and record the upsert."""

        stored_document = dict(body)
        self.items[stored_document["id"]] = stored_document
        self.upserts.append(stored_document)
        return stored_document

    def query_items(
        self,
        *,
        query: str,
        parameters: list[dict[str, Any]],
        enable_cross_partition_query: bool,
        partition_key: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return pre-seeded query results and record the query metadata."""

        self.last_query = {
            "query": query,
            "parameters": parameters,
            "enable_cross_partition_query": enable_cross_partition_query,
            "partition_key": partition_key,
        }
        return [dict(item) for item in self.query_results]


TEST_USER = UserClaims(
    sub="user-123",
    email="joey@example.com",
    name="Joey Backend",
)
OTHER_USER = UserClaims(
    sub="user-999",
    email="other@example.com",
    name="Other User",
)


@pytest.fixture
def profile() -> UserProfile:
    """Build a stable profile object reused across endpoint tests."""

    timestamp = datetime(2026, 5, 29, 16, 4, 28, tzinfo=UTC)
    return UserProfile(
        id=TEST_USER.sub,
        user_id=TEST_USER.sub,
        email=TEST_USER.email,
        name=TEST_USER.name,
        created_at=timestamp,
        updated_at=timestamp,
    )


@pytest.fixture
def history() -> list[ChatHistoryItem]:
    """Build chat history entries ordered from newest to oldest."""

    base_time = datetime(2026, 5, 29, 16, 4, 28, tzinfo=UTC)
    return [
        ChatHistoryItem(
            id="history-1",
            conversation_id="conversation-1",
            user_id=TEST_USER.sub,
            prompt="First prompt",
            response="First answer",
            created_at=base_time,
        ),
        ChatHistoryItem(
            id="history-2",
            conversation_id="conversation-2",
            user_id=TEST_USER.sub,
            prompt="Second prompt",
            response="Second answer",
            created_at=base_time - timedelta(minutes=1),
        ),
        ChatHistoryItem(
            id="history-3",
            conversation_id="conversation-3",
            user_id=TEST_USER.sub,
            prompt="Third prompt",
            response="Third answer",
            created_at=base_time - timedelta(minutes=2),
        ),
    ]


@pytest.fixture
def authenticated_client(
    profile: UserProfile,
    history: list[ChatHistoryItem],
) -> Generator[tuple[TestClient, FakeUserService], None, None]:
    """Provide a client whose requests are authenticated by override."""

    app = create_app()
    fake_service = FakeUserService(profile=profile, history=history)
    app.dependency_overrides[get_user_service] = lambda: fake_service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with TestClient(app) as client:
        yield client, fake_service

    app.dependency_overrides.clear()


@pytest.fixture
def unauthenticated_client() -> Generator[TestClient, None, None]:
    """Provide a client that keeps real auth enforcement enabled."""

    app = create_app()
    app.dependency_overrides[get_user_service] = lambda: FakeUserService()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()


def test_get_me_returns_profile(
    authenticated_client: tuple[TestClient, FakeUserService],
) -> None:
    """Return the stored profile for an authenticated caller."""

    client, _ = authenticated_client
    response = client.get("/me")

    assert response.status_code == 200
    assert response.json()["user_id"] == TEST_USER.sub
    assert response.json()["email"] == TEST_USER.email


def test_get_me_creates_profile_on_first_access(
    history: list[ChatHistoryItem],
) -> None:
    """Create a new profile document when the user has none yet."""

    app = create_app()
    fake_service = FakeUserService(profile=None, history=history)
    app.dependency_overrides[get_user_service] = lambda: fake_service
    app.dependency_overrides[get_current_user] = lambda: TEST_USER

    with TestClient(app) as client:
        response = client.get("/me")

    app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["id"] == TEST_USER.sub
    assert fake_service.profile is not None


def test_get_me_history_paginates_results(
    authenticated_client: tuple[TestClient, FakeUserService],
) -> None:
    """Return the requested page of chat history rows."""

    client, _ = authenticated_client
    response = client.get("/me/history", params={"limit": 2, "offset": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["limit"] == 2
    assert payload["offset"] == 1
    assert [item["id"] for item in payload["items"]] == [
        "history-2",
        "history-3",
    ]


def test_get_me_export_returns_all_user_data(
    authenticated_client: tuple[TestClient, FakeUserService],
) -> None:
    """Return profile and full history in the GDPR export payload."""

    client, _ = authenticated_client
    response = client.get("/me/export")

    assert response.status_code == 200
    payload = response.json()
    assert payload["profile"]["user_id"] == TEST_USER.sub
    assert len(payload["history"]) == 3
    assert payload["history"][0]["id"] == "history-1"


def test_delete_me_marks_all_user_data_for_cleanup(
    authenticated_client: tuple[TestClient, FakeUserService],
) -> None:
    """Queue cleanup for profile, history, and quota user data."""

    client, fake_service = authenticated_client
    response = client.delete("/me")

    assert response.status_code == 202
    assert response.json()["user_id"] == TEST_USER.sub
    assert response.json()["cleanup_pending"] is True
    assert response.json()["deletion_scheduled_at"] is not None
    assert fake_service.profile is not None
    assert fake_service.profile.deleted_at is not None
    assert fake_service.deleted_containers == {
        "profile",
        "history",
        "quotas",
    }


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/me"),
        ("get", "/me/history"),
        ("get", "/me/export"),
        ("delete", "/me"),
    ],
)
def test_me_endpoints_require_auth(
    unauthenticated_client: TestClient,
    method: str,
    path: str,
) -> None:
    """Reject unauthenticated requests across all /me endpoints."""

    response = getattr(unauthenticated_client, method)(path)

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header."}


def test_user_service_blocks_cross_user_history_access(
    profile: UserProfile,
) -> None:
    """Raise when a history query returns another user's document."""

    user_container = FakeContainer(
        items={profile.id: profile.model_dump(mode="json")}
    )
    history_container = FakeContainer(
        query_results=[
            {
                "id": "history-foreign",
                "conversation_id": "conversation-foreign",
                "user_id": OTHER_USER.sub,
                "prompt": "Foreign prompt",
                "response": "Foreign response",
                "created_at": datetime.now(UTC).isoformat(),
            }
        ]
    )
    quota_container = FakeContainer()
    service = UserService(
        user_container=user_container,
        history_container=history_container,
        quota_container=quota_container,
    )

    with pytest.raises(
        UserServiceError,
        match="Unauthorized history item returned for the user.",
    ):
        service.get_history(TEST_USER.sub, limit=20, offset=0)

    assert history_container.last_query is not None
    assert history_container.last_query["partition_key"] == TEST_USER.sub
    assert any(
        parameter == {"name": "@user_id", "value": TEST_USER.sub}
        for parameter in history_container.last_query["parameters"]
    )


def test_user_service_marks_profile_history_and_quotas_for_cleanup(
    profile: UserProfile,
) -> None:
    """Persist cleanup markers in every Cosmos container on delete."""

    user_container = FakeContainer(
        items={profile.id: profile.model_dump(mode="json")}
    )
    history_container = FakeContainer()
    quota_container = FakeContainer()
    service = UserService(
        user_container=user_container,
        history_container=history_container,
        quota_container=quota_container,
    )

    deleted_profile = service.soft_delete_user(TEST_USER)
    deletion_marker_id = f"deletion-marker:{TEST_USER.sub}"

    assert deleted_profile.cleanup_pending is True
    assert deleted_profile.deletion_scheduled_at is not None
    assert user_container.items[TEST_USER.sub]["cleanup_pending"] is True
    assert (
        user_container.items[deletion_marker_id]["target_container"]
        == "profile"
    )
    assert history_container.items[deletion_marker_id]["target_container"] == (
        "history"
    )
    assert quota_container.items[deletion_marker_id]["target_container"] == (
        "quotas"
    )


def test_user_service_prevents_profile_recreation_while_delete_pending(
    profile: UserProfile,
) -> None:
    """Refuse to recreate a profile while a deletion marker exists."""

    deletion_time = datetime.now(UTC).isoformat()
    user_container = FakeContainer(
        items={
            f"deletion-marker:{TEST_USER.sub}": {
                "id": f"deletion-marker:{TEST_USER.sub}",
                "user_id": TEST_USER.sub,
                "document_type": "deletion_marker",
                "target_container": "profile",
                "created_at": profile.created_at.isoformat(),
                "updated_at": deletion_time,
                "deleted_at": deletion_time,
                "cleanup_pending": True,
                "cleanup_requested_at": deletion_time,
                "deletion_scheduled_at": deletion_time,
            }
        }
    )
    history_container = FakeContainer()
    quota_container = FakeContainer()
    service = UserService(
        user_container=user_container,
        history_container=history_container,
        quota_container=quota_container,
    )

    with pytest.raises(UserDeletionPendingError):
        service.get_or_create_profile(TEST_USER)

    assert TEST_USER.sub not in user_container.items
