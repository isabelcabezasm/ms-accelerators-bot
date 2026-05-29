"""Tests for the Cosmos-backed daily chat quota service."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from azure.core import MatchConditions
from azure.cosmos.exceptions import (
    CosmosHttpResponseError,
    CosmosResourceNotFoundError,
)
from fastapi import Depends, FastAPI, HTTPException
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from src.api.auth import get_current_user
from src.api.dependencies import get_quota_service
from src.api.main import create_app
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
        *,
        create_conflicts: int = 0,
        upsert_conflicts: int = 0,
    ) -> None:
        """Seed the fake container with optional existing documents."""

        self._etag_counter = 0
        self.items = {
            item_key: self._with_etag(document)
            for item_key, document in (items or {}).items()
        }
        self.create_conflicts_remaining = create_conflicts
        self.upsert_conflicts_remaining = upsert_conflicts
        self.created_items: list[dict[str, Any]] = []
        self.upserted_items: list[dict[str, Any]] = []
        self.upsert_calls: list[dict[str, Any]] = []

    def _next_etag(self) -> str:
        """Generate a deterministic ETag for the next stored version."""

        self._etag_counter += 1
        return f"etag-{self._etag_counter}"

    def _with_etag(self, document: dict[str, Any]) -> dict[str, Any]:
        """Return a copy of the document that always includes an ETag."""

        stored_document = dict(document)
        if "_etag" not in stored_document:
            stored_document["_etag"] = self._next_etag()
        return stored_document

    def read_item(self, *, item: str, partition_key: str) -> dict[str, Any]:
        """Return the stored item for the given partition and id."""

        stored_item = self.items.get((partition_key, item))
        if stored_item is None:
            raise CosmosResourceNotFoundError(message="missing item")
        return dict(stored_item)

    def create_item(self, *, body: dict[str, Any]) -> dict[str, Any]:
        """Persist a new item or raise a conflict for concurrent writes."""

        item_key = (body["user_id"], body["id"])
        if self.create_conflicts_remaining > 0:
            self.create_conflicts_remaining -= 1
            self.items[item_key] = self._with_etag(body)
            raise CosmosHttpResponseError(status_code=409, message="conflict")

        if item_key in self.items:
            raise CosmosHttpResponseError(status_code=409, message="conflict")

        document = self._with_etag(body)
        self.items[item_key] = document
        self.created_items.append(document)
        return dict(document)

    def upsert_item(
        self,
        *,
        body: dict[str, Any],
        etag: str,
        match_condition: MatchConditions,
    ) -> dict[str, Any]:
        """Upsert an item while enforcing Cosmos optimistic locking."""

        item_key = (body["user_id"], body["id"])
        current_document = self.items.get(item_key)
        if current_document is None:
            raise CosmosResourceNotFoundError(message="missing item")

        self.upsert_calls.append(
            {
                "body": dict(body),
                "etag": etag,
                "match_condition": match_condition,
            }
        )

        if self.upsert_conflicts_remaining > 0:
            self.upsert_conflicts_remaining -= 1
            concurrent_document = dict(current_document)
            concurrent_document["count"] = int(
                concurrent_document.get("count", 0)
            ) + 1
            concurrent_document["_etag"] = self._next_etag()
            self.items[item_key] = concurrent_document
            raise CosmosHttpResponseError(
                status_code=412,
                message="etag conflict",
            )

        if (
            match_condition is MatchConditions.IfNotModified
            and current_document.get("_etag") != etag
        ):
            raise CosmosHttpResponseError(
                status_code=412,
                message="etag mismatch",
            )

        document = self._with_etag(body)
        self.items[item_key] = document
        self.upserted_items.append(document)
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
    assert container_client.created_items[0]["_etag"].startswith("etag-")


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
    """Increment an existing daily counter using conditional upsert."""

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
    assert container_client.upserted_items[0]["count"] == 2
    assert container_client.upsert_calls[0]["match_condition"] is (
        MatchConditions.IfNotModified
    )


def test_concurrent_create_retries_after_conflict() -> None:
    """Retry a create conflict and apply the second increment safely."""

    container_client = FakeContainerClient(create_conflicts=1)
    service = build_service(container_client, daily_limit=3)

    document = service.check_and_increment("user-123")

    assert document["count"] == 2
    assert len(container_client.upserted_items) == 1
    assert container_client.upserted_items[0]["count"] == 2


def test_concurrent_increment_retries_after_etag_conflict() -> None:
    """Retry a 412 conflict so concurrent requests cannot bypass quotas."""

    document_id = "user-123:2026-05-29"
    container_client = FakeContainerClient(
        items={
            ("user-123", document_id): {
                "id": document_id,
                "user_id": "user-123",
                "date": "2026-05-29",
                "count": 0,
                "ttl": COSMOS_ITEM_TTL_SECONDS,
            }
        },
        upsert_conflicts=1,
    )
    service = build_service(container_client, daily_limit=3)

    document = service.check_and_increment("user-123")

    assert document["count"] == 2
    assert len(container_client.upsert_calls) == 2
    assert container_client.upserted_items[0]["count"] == 2


def test_missing_etag_fails_closed() -> None:
    """Reject updates when Cosmos does not return the required ETag."""

    document_id = "user-123:2026-05-29"
    container_client = FakeContainerClient(
        items={
            ("user-123", document_id): {
                "id": document_id,
                "user_id": "user-123",
                "date": "2026-05-29",
                "count": 1,
                "ttl": COSMOS_ITEM_TTL_SECONDS,
                "_etag": "",
            }
        }
    )
    service = build_service(container_client, daily_limit=3)

    with pytest.raises(HTTPException) as error:
        service.check_and_increment("user-123")

    assert getattr(error.value, "status_code", None) == 503
    assert getattr(error.value, "detail", "") == (
        "Quota service is unavailable."
    )


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


def test_real_chat_route_wires_quota_dependency() -> None:
    """Attach the quota dependency to the repository's actual /chat route."""

    app = create_app()
    chat_route = next(
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path == "/chat"
    )

    dependency_calls = {
        dependency.call for dependency in chat_route.dependant.dependencies
    }

    assert enforce_daily_chat_quota in dependency_calls
