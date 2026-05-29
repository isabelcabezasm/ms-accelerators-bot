"""Tests for the Cosmos-backed daily chat quota service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from src.api.auth import get_current_user
from src.api.dependencies import get_quota_service
from src.api.models import UserClaims
from src.api.quota_dependency import enforce_daily_chat_quota
from src.api.quotas import (
    COSMOS_ITEM_TTL_SECONDS,
    QuotaExceededError,
    QuotaService,
    QuotaSettings,
)

FIXED_TIME = datetime(2026, 5, 29, 16, 4, 28, tzinfo=UTC)
VALID_ENDPOINT = "https://quota-db.documents.azure.com"


class FakeContainerClient:
    """Store quota documents in memory for deterministic tests."""

    def __init__(
        self,
        items: dict[tuple[str, str], dict[str, Any]] | None = None,
    ) -> None:
        """Seed the fake container with optional existing documents."""

        self.items = items or {}
        self.created_items: list[dict[str, Any]] = []
        self.replaced_items: list[dict[str, Any]] = []

    def read_item(self, *, item: str, partition_key: str) -> dict[str, Any]:
        """Return the stored item for the given partition and id."""

        stored_item = self.items.get((partition_key, item))
        if stored_item is None:
            raise CosmosResourceNotFoundError(message="missing item")
        return dict(stored_item)

    def create_item(self, *, body: dict[str, Any]) -> dict[str, Any]:
        """Persist a new item and capture it for assertions."""

        item_key = (body["user_id"], body["id"])
        document = dict(body)
        self.items[item_key] = document
        self.created_items.append(document)
        return dict(document)

    def replace_item(
        self,
        *,
        item: str,
        body: dict[str, Any],
        etag: str | None = None,
        match_condition: object | None = None,
    ) -> dict[str, Any]:
        """Replace an existing item while ignoring Cosmos SDK metadata."""

        del etag, match_condition
        item_key = (body["user_id"], item)
        document = dict(body)
        self.items[item_key] = document
        self.replaced_items.append(document)
        return dict(document)


def build_service(
    container_client: FakeContainerClient,
    *,
    daily_limit: int = 2,
    now_provider: Callable[[], datetime] | None = None,
) -> QuotaService:
    """Create a quota service backed by the fake Cosmos container."""

    settings = QuotaSettings(
        cosmos_endpoint=VALID_ENDPOINT,
        cosmos_database="app-db",
        cosmos_container_quotas="quotas",
        daily_chat_quota=daily_limit,
    )
    return QuotaService(
        settings=settings,
        container_client=container_client,
        now_provider=now_provider or (lambda: FIXED_TIME),
    )


@pytest.fixture
def chat_app() -> FastAPI:
    """Build a small app that applies the chat quota dependency."""

    app = FastAPI()

    @app.post("/chat", dependencies=[Depends(enforce_daily_chat_quota)])
    async def chat() -> dict[str, str]:
        """Return a stable response for quota dependency assertions."""

        return {"status": "ok"}

    return app


def test_quota_check_passes_when_under_limit() -> None:
    """Allow a request and create a new counter below the daily limit."""

    container_client = FakeContainerClient()
    service = build_service(container_client, daily_limit=2)

    document = service.check_and_increment("user-123")

    assert document["count"] == 1
    assert container_client.created_items[0]["user_id"] == "user-123"


def test_quota_check_fails_when_limit_exceeded(
    chat_app: FastAPI,
) -> None:
    """Return 429 with Retry-After once the user exhausts the quota."""

    document_id = "user-123:2026-05-29"
    container_client = FakeContainerClient(
        items={
            ("user-123", document_id): {
                "id": document_id,
                "user_id": "user-123",
                "date": "2026-05-29",
                "count": 1,
                "ttl": COSMOS_ITEM_TTL_SECONDS,
            }
        }
    )
    service = build_service(container_client, daily_limit=1)

    chat_app.dependency_overrides[get_current_user] = lambda: UserClaims(
        sub="user-123",
        email="joey@example.com",
        name="Joey Backend",
    )
    chat_app.dependency_overrides[get_quota_service] = lambda: service

    client = TestClient(chat_app)
    response = client.post("/chat")

    assert response.status_code == 429
    assert response.json() == {"detail": "Daily chat quota exceeded."}
    assert response.headers["retry-after"] == "28532"


def test_counter_increments_correctly() -> None:
    """Increment an existing daily counter on each successful request."""

    document_id = "user-123:2026-05-29"
    container_client = FakeContainerClient(
        items={
            ("user-123", document_id): {
                "id": document_id,
                "user_id": "user-123",
                "date": "2026-05-29",
                "count": 1,
                "ttl": COSMOS_ITEM_TTL_SECONDS,
            }
        }
    )
    service = build_service(container_client, daily_limit=3)

    document = service.check_and_increment("user-123")

    assert document["count"] == 2
    assert container_client.replaced_items[0]["count"] == 2


def test_ttl_is_set_on_documents() -> None:
    """Persist new quota documents with a 48-hour time-to-live."""

    container_client = FakeContainerClient()
    service = build_service(container_client)

    document = service.check_and_increment("user-123")

    assert document["ttl"] == COSMOS_ITEM_TTL_SECONDS
    assert container_client.created_items[0]["ttl"] == COSMOS_ITEM_TTL_SECONDS


def test_quota_service_raises_http_429_directly() -> None:
    """Raise the quota-specific HTTP error when the limit is exhausted."""

    document_id = "user-123:2026-05-29"
    container_client = FakeContainerClient(
        items={
            ("user-123", document_id): {
                "id": document_id,
                "user_id": "user-123",
                "date": "2026-05-29",
                "count": 2,
                "ttl": COSMOS_ITEM_TTL_SECONDS,
            }
        }
    )
    service = build_service(container_client, daily_limit=2)

    with pytest.raises(QuotaExceededError) as error:
        service.check_and_increment("user-123")

    assert error.value.status_code == 429
    assert error.value.headers == {"Retry-After": "28532"}


def test_ttl_configuration_validates_cosmos_endpoint() -> None:
    """Reject quota settings that do not target Cosmos DB endpoints."""

    with pytest.raises(ValueError, match="AZURE_COSMOS_ENDPOINT"):
        QuotaSettings(
            cosmos_endpoint="https://example.com",
            cosmos_database="app-db",
            cosmos_container_quotas="quotas",
        )


def test_quota_service_uses_managed_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Build the Cosmos client with DefaultAzureCredential."""

    container_client = FakeContainerClient()
    captured: dict[str, Any] = {}
    credential = object()

    class FakeDefaultAzureCredential:
        """Return a stable credential sentinel for assertions."""

        def __new__(cls) -> object:
            """Return the mocked managed identity credential."""

            del cls
            return credential

    class FakeDatabaseClient:
        """Return the fake quota container requested by the service."""

        def get_container_client(self, name: str) -> FakeContainerClient:
            """Capture the container name and return the fake container."""

            captured["container"] = name
            return container_client

    class FakeCosmosClient:
        """Capture the Cosmos client arguments used by the service."""

        def __init__(self, *, url: str, credential: object) -> None:
            """Store the endpoint and credential used to build the client."""

            captured["url"] = url
            captured["credential"] = credential

        def get_database_client(self, name: str) -> FakeDatabaseClient:
            """Capture the database name and return a fake database."""

            captured["database"] = name
            return FakeDatabaseClient()

    monkeypatch.setattr(
        "src.api.quotas.DefaultAzureCredential",
        FakeDefaultAzureCredential,
    )
    monkeypatch.setattr("src.api.quotas.CosmosClient", FakeCosmosClient)

    settings = QuotaSettings(
        cosmos_endpoint=VALID_ENDPOINT,
        cosmos_database="app-db",
        cosmos_container_quotas="quotas",
    )
    service = QuotaService(settings=settings, now_provider=lambda: FIXED_TIME)

    document = service.check_and_increment("user-123")

    assert document["count"] == 1
    assert captured == {
        "url": VALID_ENDPOINT,
        "credential": credential,
        "database": "app-db",
        "container": "quotas",
    }


