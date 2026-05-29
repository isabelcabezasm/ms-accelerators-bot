"""Hybrid retrieval support for the chat RAG pipeline."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from .exceptions import RAGError
from .query_rewriter import build_azure_openai_client
from .settings import RagSettings, get_rag_settings

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RetrievedChunk:
    """Represents a retrieved chunk and its citation metadata."""

    citation_id: int
    accelerator_id: str
    accelerator_name: str
    chunk_id: str
    url: str
    excerpt: str


@dataclass(slots=True)
class RetrievedAccelerator:
    """Represents grouped chunks for a single accelerator."""

    accelerator_id: str
    accelerator_name: str
    url: str
    summary: str
    chunks: list[RetrievedChunk] = field(default_factory=list)


class HybridRetriever:
    """Runs hybrid search and groups results by accelerator."""

    def __init__(
        self,
        *,
        settings: RagSettings | None = None,
        search_client: SearchClient | Any | None = None,
        openai_client: Any | None = None,
    ) -> None:
        """Initializes the retriever with Azure clients and settings."""

        self._settings = settings or get_rag_settings()
        self._search_client = search_client or self._build_search_client(
            self._settings
        )
        self._openai_client = openai_client or build_azure_openai_client(
            self._settings
        )

    def _build_search_client(self, settings: RagSettings) -> SearchClient:
        """Builds a managed-identity SearchClient instance."""

        return SearchClient(
            endpoint=settings.require_search_endpoint(),
            index_name=settings.require_search_index_name(),
            credential=DefaultAzureCredential(),
        )

    def retrieve(self, query: str) -> list[RetrievedAccelerator]:
        """Retrieves and groups chunks relevant to the rewritten query."""

        try:
            embedding = self._embed_query(query)
            results = self._search_client.search(
                search_text=query,
                top=self._settings.top_k,
                select=[
                    "id",
                    "parent_id",
                    "title",
                    "url",
                    "content",
                    "long_description",
                ],
                query_type="semantic",
                semantic_configuration_name=(
                    self._settings.semantic_configuration_name
                ),
                vector_queries=[
                    VectorizedQuery(
                        vector=embedding,
                        k_nearest_neighbors=self._settings.top_k,
                        fields="content_vector",
                    )
                ],
            )
        except Exception as exc:
            LOGGER.exception("Failed to retrieve search results.")
            raise RAGError("Unable to retrieve supporting documents.") from exc

        grouped_results: dict[str, RetrievedAccelerator] = {}
        for citation_id, result in enumerate(results, start=1):
            document = self._coerce_mapping(result)
            accelerator_id = str(
                document.get("parent_id") or document.get("id") or citation_id
            )
            accelerator_name = str(
                document.get("title") or document.get("parent_id") or "Unknown"
            )
            url = str(document.get("url") or "")
            excerpt = str(document.get("content") or "").strip()
            chunk_id = str(document.get("id") or f"chunk-{citation_id}")
            summary = str(document.get("long_description") or excerpt)

            if not excerpt:
                continue

            if accelerator_id not in grouped_results:
                grouped_results[accelerator_id] = RetrievedAccelerator(
                    accelerator_id=accelerator_id,
                    accelerator_name=accelerator_name,
                    url=url,
                    summary=summary,
                )

            grouped_results[accelerator_id].chunks.append(
                RetrievedChunk(
                    citation_id=citation_id,
                    accelerator_id=accelerator_id,
                    accelerator_name=accelerator_name,
                    chunk_id=chunk_id,
                    url=url,
                    excerpt=excerpt,
                )
            )

        return list(grouped_results.values())

    def _embed_query(self, query: str) -> Sequence[float]:
        """Creates an embedding for hybrid vector search."""

        try:
            response = self._openai_client.embeddings.create(
                model=self._settings.require_embedding_deployment(),
                input=query,
            )
        except Exception as exc:
            LOGGER.exception("Failed to create a query embedding.")
            raise RAGError("Unable to embed the search query.") from exc

        data = getattr(response, "data", [])
        if not data:
            raise RAGError("Embedding response did not contain vectors.")
        return data[0].embedding

    def _coerce_mapping(self, result: Any) -> Mapping[str, Any]:
        """Normalizes SearchClient results into a mapping."""

        if isinstance(result, Mapping):
            return result
        if hasattr(result, "items"):
            return dict(result.items())
        msg = "Search result payload must be a mapping."
        raise RAGError(msg)
