"""Tests for authenticated /me API endpoints."""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime, timedelta

import pytest
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
        self.profile = profile.model_copy(
            update={
                "deleted_at": deleted_at,
                "cleanup_pending": True,
                "cleanup_requested_at": deleted_at,
                "updated_at": deleted_at,
            }
        )
        return self.profile


TEST_USER = UserClaims(
    sub="user-123",
    email="joey@example.com",
    name="Joey Backend",
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


def test_delete_me_marks_profile_for_cleanup(
    authenticated_client: tuple[TestClient, FakeUserService],
) -> None:
    """Mark the user as deleted and pending background cleanup."""

    client, fake_service = authenticated_client
    response = client.delete("/me")

    assert response.status_code == 202
    assert response.json()["user_id"] == TEST_USER.sub
    assert response.json()["cleanup_pending"] is True
    assert fake_service.profile is not None
    assert fake_service.profile.deleted_at is not None


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
