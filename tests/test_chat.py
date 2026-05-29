"""Tests for the authenticated chat endpoint and RAG pipeline."""

from __future__ import annotations

from collections.abc import Generator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from src.api.auth import get_current_user
from src.api.main import app
from src.api.models import UserClaims
from src.api.rag import (
    AnswerGenerator,
    GeneratedAnswer,
    HybridRetriever,
    QueryRewriter,
    RagSettings,
    RetrievedAccelerator,
    RetrievedChunk,
)
from src.api.routes.chat import (
    get_answer_generator,
    get_hybrid_retriever,
    get_query_rewriter,
)


class StubQueryRewriter:
    """Simple query rewriter double for route tests."""

    def rewrite_query(self, message: str) -> str:
        """Return a deterministic rewritten query for assertions."""

        return f"rewritten: {message}"


class StubRetriever:
    """Simple retriever double for route tests."""

    def retrieve(self, query: str) -> list[RetrievedAccelerator]:
        """Return a single grouped accelerator result."""

        return [
            RetrievedAccelerator(
                accelerator_id="acc-1",
                accelerator_name="Copilot Accelerator",
                url="https://contoso.example/accelerators/copilot",
                summary="Copilot implementation guidance.",
                chunks=[
                    RetrievedChunk(
                        citation_id=1,
                        accelerator_id="acc-1",
                        accelerator_name="Copilot Accelerator",
                        chunk_id="chunk-1",
                        url=(
                            "https://contoso.example/accelerators/copilot"
                        ),
                        excerpt="Copilot accelerators help teams ship faster.",
                    )
                ],
            )
        ]


class StubGenerator:
    """Simple answer generator double for route tests."""

    def generate_answer(
        self,
        *,
        message: str,
        rewritten_query: str,
        accelerators: list[RetrievedAccelerator],
    ) -> GeneratedAnswer:
        """Return a deterministic answer that includes one citation."""

        del message, rewritten_query
        chunk = accelerators[0].chunks[0]
        return GeneratedAnswer(
            answer="Copilot accelerators help teams ship faster [1].",
            citations=[
                {
                    "id": chunk.citation_id,
                    "accelerator_id": chunk.accelerator_id,
                    "accelerator_name": chunk.accelerator_name,
                    "chunk_id": chunk.chunk_id,
                    "url": chunk.url,
                    "excerpt": chunk.excerpt,
                }
            ],
        )


class MockChatResponse:
    """Minimal Azure OpenAI chat response payload."""

    def __init__(self, content: str) -> None:
        """Store the message content returned by the mock client."""

        self.choices = [
            SimpleNamespace(message=SimpleNamespace(content=content))
        ]


class MockEmbeddingResponse:
    """Minimal Azure OpenAI embedding response payload."""

    def __init__(self, embedding: list[float]) -> None:
        """Store the embedding vector for retriever assertions."""

        self.data = [SimpleNamespace(embedding=embedding)]


class MockChatCompletions:
    """Mock Azure OpenAI chat completions client."""

    def __init__(self, responses: list[str]) -> None:
        """Queue the responses returned for successive chat calls."""

        self._responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> MockChatResponse:
        """Return the next queued chat completion response."""

        self.calls.append(kwargs)
        return MockChatResponse(self._responses.pop(0))


class MockEmbeddings:
    """Mock Azure OpenAI embeddings client."""

    def __init__(self) -> None:
        """Initialize the recorded embedding calls."""

        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> MockEmbeddingResponse:
        """Return a deterministic embedding vector."""

        self.calls.append(kwargs)
        return MockEmbeddingResponse([0.1, 0.2, 0.3])


class MockOpenAIClient:
    """Mock Azure OpenAI client exposing chat and embeddings APIs."""

    def __init__(self, responses: list[str]) -> None:
        """Compose mocked chat and embedding endpoints."""

        self.chat = SimpleNamespace(
            completions=MockChatCompletions(responses)
        )
        self.embeddings = MockEmbeddings()


class MockSearchClient:
    """Mock Azure AI Search client for hybrid retrieval tests."""

    def __init__(self, results: list[dict[str, Any]]) -> None:
        """Store the search results returned by the mock client."""

        self._results = results
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> list[dict[str, Any]]:
        """Return deterministic search results for the retriever."""

        self.calls.append(kwargs)
        return self._results


@pytest.fixture(autouse=True)
def clear_dependency_overrides() -> Generator[None, None, None]:
    """Reset FastAPI dependency overrides between chat tests."""

    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


@pytest.fixture
def authenticated_user() -> UserClaims:
    """Return a reusable authenticated user for protected route tests."""

    return UserClaims(
        sub="user-123",
        email="joey@example.com",
        name="Joey Backend",
    )


def test_authenticated_chat_request_succeeds(
    client: TestClient,
    authenticated_user: UserClaims,
) -> None:
    """Return a chat answer when the caller is authenticated."""

    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    app.dependency_overrides[get_query_rewriter] = StubQueryRewriter
    app.dependency_overrides[get_hybrid_retriever] = StubRetriever
    app.dependency_overrides[get_answer_generator] = StubGenerator

    response = client.post(
        "/chat",
        json={
            "message": "How can Copilot accelerators help my team?",
            "conversation_id": "conv-123",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "answer": "Copilot accelerators help teams ship faster [1].",
        "citations": [
            {
                "id": 1,
                "accelerator_id": "acc-1",
                "accelerator_name": "Copilot Accelerator",
                "chunk_id": "chunk-1",
                "url": "https://contoso.example/accelerators/copilot",
                "excerpt": (
                    "Copilot accelerators help teams ship faster."
                ),
            }
        ],
        "conversation_id": "conv-123",
    }


def test_chat_requires_authentication(client: TestClient) -> None:
    """Reject unauthenticated chat requests with a 401 response."""

    app.dependency_overrides[get_query_rewriter] = StubQueryRewriter
    app.dependency_overrides[get_hybrid_retriever] = StubRetriever
    app.dependency_overrides[get_answer_generator] = StubGenerator

    response = client.post("/chat", json={"message": "Hello there"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header."}


def test_rag_flow_produces_answer_with_citations() -> None:
    """Run the end-to-end RAG components with mocked Azure clients."""

    settings = RagSettings(
        azure_openai_endpoint="https://unit.openai.azure.com",
        azure_openai_chat_deployment="gpt-4.1",
        azure_search_endpoint="https://unit.search.windows.net",
        azure_search_index_name="accelerators-index",
    )
    openai_client = MockOpenAIClient(
        responses=[
            "copilot accelerator implementation guidance",
            (
                '{"answer": "Use the Copilot accelerator [1].", '
                '"citations": [1]}'
            ),
        ]
    )
    search_client = MockSearchClient(
        results=[
            {
                "id": "chunk-1",
                "parent_id": "acc-1",
                "title": "Copilot Accelerator",
                "url": "https://contoso.example/accelerators/copilot",
                "content": "Copilot accelerators include implementation "
                "guidance and sample assets.",
                "long_description": "Copilot accelerator reference.",
            }
        ]
    )

    rewriter = QueryRewriter(settings=settings, openai_client=openai_client)
    retriever = HybridRetriever(
        settings=settings,
        search_client=search_client,
        openai_client=openai_client,
    )
    generator = AnswerGenerator(settings=settings, openai_client=openai_client)

    rewritten_query = rewriter.rewrite_query("How do I use Copilot?")
    accelerators = retriever.retrieve(rewritten_query)
    generated_answer = generator.generate_answer(
        message="How do I use Copilot?",
        rewritten_query=rewritten_query,
        accelerators=accelerators,
    )

    assert rewritten_query == "copilot accelerator implementation guidance"
    assert len(accelerators) == 1
    assert generated_answer.answer == "Use the Copilot accelerator [1]."
    assert generated_answer.citations[0].accelerator_name == (
        "Copilot Accelerator"
    )
    assert search_client.calls[0]["search_text"] == rewritten_query
    assert openai_client.embeddings.calls[0]["input"] == rewritten_query


def test_chat_rejects_empty_message(
    client: TestClient,
    authenticated_user: UserClaims,
) -> None:
    """Reject whitespace-only chat messages with validation errors."""

    app.dependency_overrides[get_current_user] = lambda: authenticated_user
    app.dependency_overrides[get_query_rewriter] = StubQueryRewriter
    app.dependency_overrides[get_hybrid_retriever] = StubRetriever
    app.dependency_overrides[get_answer_generator] = StubGenerator

    response = client.post("/chat", json={"message": "   "})

    assert response.status_code == 422
    error_message = response.json()["detail"][0]["msg"]
    assert error_message == (
        "Value error, message must not be empty."
    )
