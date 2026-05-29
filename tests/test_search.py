"""Tests for the FastAPI hybrid search endpoint."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api.dependencies import get_search_service
from src.api.main import app
from src.api.models import SearchResult
from src.api.rate_limit import InMemoryRateLimiter, get_rate_limiter
from src.api.search_service import SearchService, SearchServiceSettings


@dataclass(frozen=True)
class FakeEmbedding:
    """Represent a fake embedding payload returned by Azure OpenAI."""

    embedding: list[float]


@dataclass(frozen=True)
class FakeEmbeddingResponse:
    """Wrap fake embedding items in an Azure OpenAI-like response."""

    data: list[FakeEmbedding]


class FakeEmbeddingsAPI:
    """Collect embedding calls and return deterministic vectors."""

    def __init__(self) -> None:
        """Initialize the fake embeddings endpoint."""

        self.calls: list[dict[str, Any]] = []

    def create(self, *, model: str, input: list[str]) -> FakeEmbeddingResponse:
        """Return one small vector for the supplied query text."""

        self.calls.append({"model": model, "input": input})
        return FakeEmbeddingResponse(data=[FakeEmbedding([0.1, 0.2, 0.3])])


class FakeOpenAIClient:
    """Expose the fake embeddings API on an AzureOpenAI-like client."""

    def __init__(self) -> None:
        """Initialize the fake client surface."""

        self.embeddings = FakeEmbeddingsAPI()


class FakeSearchClient:
    """Record search calls and return deterministic Azure Search results."""

    def __init__(self) -> None:
        """Initialize the fake search client state."""

        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Store the request shape and return one ranked document."""

        self.calls.append(kwargs)
        return [
            {
                "parent_id": "accelerator-1",
                "name": "Contoso Search Accelerator",
                "summary": "Semantic search over product data.",
                "long_description": "Long description.",
                "url": "https://accelerators.ms/contoso-search",
                "@search.score": 1.25,
                "@search.reranker_score": 2.5,
                "@search.captions": [
                    {"text": "Semantic search over product data."}
                ],
            }
        ]


class StubSearchService:
    """Return static search results for route-level tests."""

    def __init__(self, results: list[SearchResult]) -> None:
        """Store the fixed result set for later calls."""

        self._results = results
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, top: int) -> list[SearchResult]:
        """Record each invocation and return the configured payload."""

        self.calls.append((query, top))
        return self._results


@pytest.fixture(autouse=True)
def clear_overrides() -> Iterator[None]:
    """Reset FastAPI dependency overrides around each test."""

    app.dependency_overrides.clear()
    get_rate_limiter.cache_clear()
    get_search_service.cache_clear()
    yield
    app.dependency_overrides.clear()
    get_rate_limiter.cache_clear()
    get_search_service.cache_clear()


def test_search_service_runs_hybrid_query() -> None:
    """Build vector and semantic inputs before querying Azure Search."""

    fake_search_client = FakeSearchClient()
    fake_openai_client = FakeOpenAIClient()
    service = SearchService(
        settings=SearchServiceSettings(
            search_endpoint="https://example.search.windows.net",
            openai_endpoint="https://example.openai.azure.com",
            openai_embedding_deployment="text-embedding-3-large",
        ),
        search_client=fake_search_client,
        openai_client=fake_openai_client,
    )

    results = service.search("semantic search", top=3)

    assert len(results) == 1
    assert results[0].title == "Contoso Search Accelerator"
    assert results[0].description == "Semantic search over product data."
    assert results[0].score == 2.5
    assert results[0].url == "https://accelerators.ms/contoso-search"
    assert fake_openai_client.embeddings.calls == [
        {
            "model": "text-embedding-3-large",
            "input": ["semantic search"],
        }
    ]
    search_call = fake_search_client.calls[0]
    assert search_call["search_text"] == "semantic search"
    assert search_call["semantic_query"] == "semantic search"
    assert search_call["semantic_configuration_name"] == (
        "default-semantic-config"
    )
    vector_query = search_call["vector_queries"][0]
    assert vector_query.fields == "content_vector"
    assert vector_query.k_nearest_neighbors == 9
    assert vector_query.vector == [0.1, 0.2, 0.3]


def test_search_endpoint_returns_ranked_results(client: TestClient) -> None:
    """Return the ranked results payload from the public endpoint."""

    stub_service = StubSearchService(
        [
            SearchResult(
                title="Contoso Search Accelerator",
                description="Semantic search over product data.",
                score=2.5,
                url="https://accelerators.ms/contoso-search",
            )
        ]
    )
    app.dependency_overrides[get_search_service] = lambda: stub_service
    app.dependency_overrides[get_rate_limiter] = lambda: InMemoryRateLimiter(
        max_requests=10,
        window_seconds=60,
    )

    response = client.get("/search", params={"q": "semantic search", "top": 3})

    assert response.status_code == 200
    assert response.json() == {
        "query": "semantic search",
        "top": 3,
        "results": [
            {
                "title": "Contoso Search Accelerator",
                "description": "Semantic search over product data.",
                "score": 2.5,
                "url": "https://accelerators.ms/contoso-search",
            }
        ],
    }
    assert stub_service.calls == [("semantic search", 3)]


def test_search_endpoint_rejects_blank_queries(client: TestClient) -> None:
    """Reject search requests that only contain whitespace."""

    app.dependency_overrides[get_search_service] = (
        lambda: StubSearchService([])
    )
    app.dependency_overrides[get_rate_limiter] = lambda: InMemoryRateLimiter(
        max_requests=10,
        window_seconds=60,
    )

    response = client.get("/search", params={"q": "   "})

    assert response.status_code == 422
    assert response.json()["detail"] == "Query must not be empty."


def test_search_endpoint_rate_limits_anonymous_callers(
    client: TestClient,
) -> None:
    """Return HTTP 429 after the in-memory request budget is exhausted."""

    limiter = InMemoryRateLimiter(
        max_requests=1,
        window_seconds=60,
    )
    app.dependency_overrides[get_search_service] = (
        lambda: StubSearchService([])
    )
    app.dependency_overrides[get_rate_limiter] = lambda: limiter

    first_response = client.get("/search", params={"q": "semantic search"})
    second_response = client.get("/search", params={"q": "semantic search"})

    assert first_response.status_code == 200
    assert second_response.status_code == 429
    assert second_response.json()["detail"] == (
        "Rate limit exceeded. Try again later."
    )
    assert int(second_response.headers["Retry-After"]) >= 1


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.search.windows.net",
        "https://example.contoso.net",
    ],
)
def test_search_service_settings_reject_invalid_search_endpoints(
    endpoint: str,
) -> None:
    """Reject non-HTTPS or non-Azure Search endpoints."""

    with pytest.raises(ValidationError):
        SearchServiceSettings(
            search_endpoint=endpoint,
            openai_endpoint="https://example.openai.azure.com",
            openai_embedding_deployment="text-embedding-3-large",
        )
