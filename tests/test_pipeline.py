"""Tests for the ingestion normalize-chunk-embed pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pytest
import tiktoken
from pydantic import ValidationError
from src.ingestion.pipeline import (
    IngestionPipeline,
    PipelineSettings,
    chunk,
    normalize,
)
from src.ingestion.search_client import (
    AcceleratorSearchClient,
    SearchSettings,
)
from src.shared.models import AcceleratorChunk, AcceleratorDocument


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
        """Return one short vector per input string."""

        self.calls.append({"model": model, "input": input})
        vectors = [
            FakeEmbedding([float(index), float(len(text))])
            for index, text in enumerate(input)
        ]
        return FakeEmbeddingResponse(data=vectors)


class FakeOpenAIClient:
    """Expose the fake embeddings API on an AzureOpenAI-like client."""

    def __init__(self) -> None:
        """Initialize the fake client surface."""

        self.embeddings = FakeEmbeddingsAPI()


@dataclass(frozen=True)
class FakeIndexingResult:
    """Represent a successful Search indexing result."""

    key: str
    succeeded: bool = True


class FakeIndexClient:
    """Record index create-or-update calls for assertions."""

    def __init__(self) -> None:
        """Initialize the fake index client."""

        self.created_indexes: list[dict[str, Any]] = []

    def create_or_update_index(
        self,
        index: dict[str, Any],
        *,
        allow_index_downtime: bool | None = None,
    ) -> dict[str, Any]:
        """Store the latest requested index definition."""

        assert allow_index_downtime is True
        self.created_indexes.append(index)
        return index


class FakeSearchClient:
    """Simulate Azure AI Search reads and writes for tests."""

    def __init__(self, existing_hashes: dict[str, str] | None = None) -> None:
        """Initialize the fake search client state."""

        self.existing_hashes = existing_hashes or {}
        self.upserted_documents: list[dict[str, Any]] = []
        self.search_filters: list[str] = []

    def search(
        self,
        *,
        search_text: str,
        filter: str,
        top: int,
        select: list[str],
    ) -> list[dict[str, str]]:
        """Return a stored content hash for the requested parent ID."""

        assert search_text == "*"
        assert top == 1
        assert select == ["parent_id", "content_hash"]
        self.search_filters.append(filter)
        parent_id = filter.split("'")[1]
        if parent_id not in self.existing_hashes:
            return []
        return [
            {
                "parent_id": parent_id,
                "content_hash": self.existing_hashes[parent_id],
            }
        ]

    def merge_or_upload_documents(
        self,
        documents: list[dict[str, Any]],
    ) -> list[FakeIndexingResult]:
        """Store uploaded documents and report success."""

        self.upserted_documents.extend(documents)
        return [
            FakeIndexingResult(key=document["id"])
            for document in documents
        ]


@pytest.fixture
def tokenizer() -> tiktoken.Encoding:
    """Return the tokenizer used by the pipeline."""

    return tiktoken.get_encoding("cl100k_base")



def test_normalize_builds_document_schema() -> None:
    """Normalize raw crawler data into the shared accelerator schema."""

    raw_document = {
        "name": " Document Intelligence Accelerator ",
        "url": "https://accelerators.ms/document-intelligence",
        "repo_url": "https://github.com/example/document-intelligence",
        "summary": "  Extract structured data  from PDFs. ",
        "readme": "Intro line.\n\nSecond paragraph with more detail.",
        "categories": "Document Processing, AI",
        "industries": ["Retail", "Retail", "Finance"],
        "azure_services": ["Azure OpenAI", "AI Search"],
        "languages": "Python\nTypeScript",
        "deployment": ["azd", "Bicep"],
        "last_updated": "2026-05-01",
        "stars": "42",
    }

    document = normalize(raw_document)

    assert document.id == "accelerator-document-intelligence-accelerator"
    assert document.github_url == (
        "https://github.com/example/document-intelligence"
    )
    assert document.summary == "Extract structured data from PDFs."
    assert document.long_description == (
        "Intro line.\n\nSecond paragraph with more detail."
    )
    assert document.categories == ["Document Processing", "AI"]
    assert document.industries == ["Retail", "Finance"]
    assert document.languages == ["Python", "TypeScript"]
    assert document.last_updated == date(2026, 5, 1)
    assert document.stars == 42
    assert len(document.content_hash) == 64



def test_chunk_adds_overlap_and_deterministic_ids(
    tokenizer: tiktoken.Encoding,
) -> None:
    """Chunk long text with token overlap and stable chunk identifiers."""

    document = AcceleratorDocument(
        id="accelerator-test",
        name="Test Accelerator",
        url="https://accelerators.ms/test",
        summary="Summary",
        long_description=(
            "Paragraph one introduces the accelerator.\n\n"
            "Paragraph two expands on the architecture and services.\n\n"
            "Paragraph three explains deployment and operations."
        ),
        categories=["AI"],
        industries=["Retail"],
        azure_services=["Azure OpenAI"],
        languages=["Python"],
        deployment=["azd"],
        content_hash="hash-1",
    )

    first_run = chunk(document, max_tokens=14, overlap=4, encoding=tokenizer)
    second_run = chunk(document, max_tokens=14, overlap=4, encoding=tokenizer)

    assert len(first_run) >= 2
    assert [item.chunk_id for item in first_run] == [
        item.chunk_id for item in second_run
    ]
    overlap_text = tokenizer.decode(
        tokenizer.encode(first_run[0].content)[-4:]
    )
    assert first_run[1].content.startswith(overlap_text)
    assert all(item.parent_id == document.id for item in first_run)
    assert all(
        len(tokenizer.encode(item.content)) <= 14 for item in first_run
    )



def test_embed_batches_requests_at_sixteen() -> None:
    """Split embedding requests into Azure OpenAI batches of sixteen."""

    openai_client = FakeOpenAIClient()
    search_client = AcceleratorSearchClient(
        settings=SearchSettings(
            search_endpoint="https://example.search.windows.net"
        ),
        index_client=FakeIndexClient(),
        search_client=FakeSearchClient(),
    )
    pipeline = IngestionPipeline(
        search_client=search_client,
        openai_client=openai_client,
        settings=PipelineSettings(
            openai_endpoint="https://example.openai.azure.com"
        ),
    )
    chunks = [
        AcceleratorChunk(
            chunk_id=f"chunk-{index}",
            parent_id="accelerator-a",
            chunk_index=index,
            name="Accelerator A",
            summary="Summary",
            content=f"Chunk content {index}",
            url="https://accelerators.ms/a",
            content_hash="hash-a",
        )
        for index in range(17)
    ]

    embedded_chunks = pipeline.embed(chunks)

    assert len(openai_client.embeddings.calls) == 2
    assert len(openai_client.embeddings.calls[0]["input"]) == 16
    assert len(openai_client.embeddings.calls[1]["input"]) == 1
    assert len(embedded_chunks) == 17
    assert embedded_chunks[0].content_vector



def test_run_skips_unchanged_documents_and_upserts_changed_chunks() -> None:
    """Only changed documents should be chunked, embedded, and upserted."""

    unchanged_document = normalize(
        {
            "id": "accelerator-unchanged",
            "name": "Unchanged Accelerator",
            "url": "https://accelerators.ms/unchanged",
            "summary": "Summary",
            "readme": "Short body.",
        }
    )
    changed_document = {
        "id": "accelerator-changed",
        "name": "Changed Accelerator",
        "url": "https://accelerators.ms/changed",
        "summary": "Updated summary",
        "readme": "Paragraph one. Paragraph two. Paragraph three.",
    }
    index_client = FakeIndexClient()
    search_client = FakeSearchClient(
        existing_hashes={
            unchanged_document.id: unchanged_document.content_hash,
            "accelerator-changed": "different-hash",
        }
    )
    pipeline = IngestionPipeline(
        search_client=AcceleratorSearchClient(
            settings=SearchSettings(
                search_endpoint="https://example.search.windows.net"
            ),
            index_client=index_client,
            search_client=search_client,
        ),
        openai_client=FakeOpenAIClient(),
        settings=PipelineSettings(
            openai_endpoint="https://example.openai.azure.com"
        ),
    )

    result = pipeline.run([unchanged_document, changed_document])

    assert result.normalized_documents == 2
    assert result.changed_documents == 1
    assert result.skipped_documents == 1
    assert result.upserted_chunks >= 1
    assert len(index_client.created_indexes) == 1
    assert all(
        document["parent_id"] == "accelerator-changed"
        for document in search_client.upserted_documents
    )
    created_index = index_client.created_indexes[0]
    fields = {
        field_definition["name"]: field_definition
        for field_definition in created_index["fields"]
    }
    assert fields["content_vector"]["dimensions"] == 3072
    semantic_config = created_index["semantic"]["configurations"][0]
    assert semantic_config["prioritizedFields"]["titleField"] == {
        "fieldName": "name"
    }


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://contoso.openai.azure.com",
        "https://contoso.example.com",
    ],
)
def test_pipeline_settings_reject_invalid_openai_endpoints(
    endpoint: str,
) -> None:
    """Reject non-Azure or non-HTTPS Azure OpenAI endpoints."""

    with pytest.raises(ValidationError, match="ACCELERATORS_OPENAI_ENDPOINT"):
        PipelineSettings(openai_endpoint=endpoint)


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://contoso.search.windows.net",
        "https://contoso.example.com",
    ],
)
def test_search_settings_reject_invalid_search_endpoints(
    endpoint: str,
) -> None:
    """Reject non-Azure or non-HTTPS Azure AI Search endpoints."""

    with pytest.raises(ValidationError, match="ACCELERATORS_SEARCH_ENDPOINT"):
        SearchSettings(search_endpoint=endpoint)


@pytest.mark.parametrize("endpoint", [None, "", "   ", "None"])
def test_pipeline_raises_for_missing_openai_endpoint(
    endpoint: str | None,
) -> None:
    """Raise a ValueError when the OpenAI endpoint is missing."""

    search_client = AcceleratorSearchClient(
        settings=SearchSettings(
            search_endpoint="https://example.search.windows.net"
        ),
        index_client=FakeIndexClient(),
        search_client=FakeSearchClient(),
    )
    settings = PipelineSettings.model_construct(
        openai_endpoint=endpoint,
        openai_api_version="2024-10-21",
        openai_embedding_deployment="text-embedding-3-large",
    )

    with pytest.raises(ValueError, match="ACCELERATORS_OPENAI_ENDPOINT"):
        IngestionPipeline(search_client=search_client, settings=settings)


@pytest.mark.parametrize("endpoint", [None, "", "   ", "None"])
def test_search_client_raises_for_missing_search_endpoint(
    endpoint: str | None,
) -> None:
    """Raise a ValueError when the Search endpoint is missing."""

    settings = SearchSettings.model_construct(
        search_endpoint=endpoint,
        search_index_name="accelerators-index",
        semantic_configuration_name="default-semantic-config",
        embedding_dimensions=3072,
        upsert_batch_size=100,
        retry_attempts=3,
    )

    with pytest.raises(ValueError, match="ACCELERATORS_SEARCH_ENDPOINT"):
        AcceleratorSearchClient(settings=settings)
