from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from .exceptions import RAGError
from .query_rewriter import build_azure_openai_client
from .settings import RagSettings, get_rag_settings

try:
    import tiktoken
except ImportError:  # pragma: no cover - dependency is available in runtime.
    tiktoken = None

logger = logging.getLogger(__name__)
MAX_SUMMARY_TOKENS = 128


@dataclass(slots=True)
class RetrievedChunk:
    """A retrievable search chunk that can be cited in a response."""

    citation_id: int
    accelerator_id: str
    accelerator_name: str
    chunk_id: str
    url: str
    excerpt: str


@dataclass(slots=True)
class RetrievedAccelerator:
    """Grouped search results for a single accelerator."""

    accelerator_id: str
    accelerator_name: str
    url: str
    summary: str
    chunks: list[RetrievedChunk] = field(default_factory=list)


def is_trusted_citation_url(
    url: str,
    trusted_domains: Sequence[str],
) -> bool:
    """Return whether a citation URL points at an approved domain."""

    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname:
        return False

    normalized_domains = [
        domain.strip().lower()
        for domain in trusted_domains
        if domain.strip()
    ]
    return any(
        hostname == domain or hostname.endswith(f".{domain}")
        for domain in normalized_domains
    )


class HybridRetriever:
    """Retrieve accelerator content from Azure AI Search."""

    def __init__(
        self,
        *,
        settings: RagSettings | None = None,
        search_client: SearchClient | Any | None = None,
        openai_client: Any | None = None,
    ) -> None:
        """Create a retriever backed by Azure Search and OpenAI."""

        self._settings = settings or get_rag_settings()
        self._search_client = search_client or self._build_search_client(
            self._settings
        )
        self._openai_client = openai_client or build_azure_openai_client(
            self._settings
        )
        self._encoding = self._build_token_encoder()

    def retrieve(self, query: str) -> list[RetrievedAccelerator]:
        """Retrieve and budget grounded accelerator search results."""

        try:
            query_vector = self._embed_query(query)
            raw_results = self._search_client.search(
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
                        vector=query_vector,
                        k_nearest_neighbors=self._settings.top_k,
                        fields="content_vector",
                    )
                ],
            )
        except Exception as exc:
            logger.exception("Failed to retrieve accelerator search results.")
            raise RAGError("Unable to retrieve accelerator context.") from exc

        grouped: dict[str, RetrievedAccelerator] = {}
        used_tokens = 0
        citation_id = 1

        for raw_result in raw_results:
            mapping = self._coerce_mapping(raw_result)
            url = self._validate_citation_url(
                self._clean_text(mapping.get("url"))
            )
            if not url:
                continue

            accelerator_id = self._clean_text(
                mapping.get("parent_id") or mapping.get("id")
            )
            if not accelerator_id:
                continue

            accelerator_name = self._clean_text(mapping.get("title"))
            if not accelerator_name:
                accelerator_name = accelerator_id

            used_tokens, added = self._add_chunk_with_budget(
                grouped=grouped,
                citation_id=citation_id,
                accelerator_id=accelerator_id,
                accelerator_name=accelerator_name,
                chunk_id=self._clean_text(mapping.get("id")) or accelerator_id,
                url=url,
                summary=self._clean_text(mapping.get("long_description")),
                excerpt=self._clean_text(mapping.get("content")),
                used_tokens=used_tokens,
            )
            if added:
                citation_id += 1

            if used_tokens >= self._settings.context_token_budget:
                logger.info("Stopped retrieval after reaching token budget.")
                break

        return [
            accelerator
            for accelerator in grouped.values()
            if accelerator.chunks
        ]

    def _add_chunk_with_budget(
        self,
        *,
        grouped: dict[str, RetrievedAccelerator],
        citation_id: int,
        accelerator_id: str,
        accelerator_name: str,
        chunk_id: str,
        url: str,
        summary: str,
        excerpt: str,
        used_tokens: int,
    ) -> tuple[int, bool]:
        """Add a chunk while keeping the accumulated context in budget."""

        if not excerpt:
            return used_tokens, False

        remaining_tokens = self._settings.context_token_budget - used_tokens
        if remaining_tokens <= 0:
            return used_tokens, False

        accelerator = grouped.get(accelerator_id)
        summary_to_store = ""
        summary_tokens = 0

        if accelerator is None and summary:
            summary_budget = min(remaining_tokens, MAX_SUMMARY_TOKENS)
            summary_to_store = self._truncate_to_token_budget(
                summary,
                summary_budget,
            )
            summary_tokens = self._count_tokens(summary_to_store)

        excerpt_budget = remaining_tokens - summary_tokens
        excerpt_to_store = self._truncate_to_token_budget(
            excerpt,
            excerpt_budget,
        )

        if not excerpt_to_store and summary_tokens > 0:
            summary_to_store = ""
            summary_tokens = 0
            excerpt_to_store = self._truncate_to_token_budget(
                excerpt,
                remaining_tokens,
            )

        if not excerpt_to_store:
            return used_tokens, False

        if accelerator is None:
            accelerator = RetrievedAccelerator(
                accelerator_id=accelerator_id,
                accelerator_name=accelerator_name,
                url=url,
                summary=summary_to_store,
            )
            grouped[accelerator_id] = accelerator

        accelerator.chunks.append(
            RetrievedChunk(
                citation_id=citation_id,
                accelerator_id=accelerator_id,
                accelerator_name=accelerator_name,
                chunk_id=chunk_id,
                url=url,
                excerpt=excerpt_to_store,
            )
        )
        updated_tokens = used_tokens + summary_tokens
        updated_tokens += self._count_tokens(excerpt_to_store)
        return updated_tokens, True

    def _validate_citation_url(self, url: str) -> str | None:
        """Return a trusted citation URL, or ``None`` for untrusted ones."""

        if is_trusted_citation_url(
            url,
            self._settings.trusted_citation_domains,
        ):
            return url

        if url:
            logger.warning(
                "Skipping search result with untrusted citation URL.",
                extra={"url": url},
            )
        return None

    def _clean_text(self, value: Any) -> str:
        """Normalize raw search fields into compact prompt-safe text."""

        if value is None:
            return ""
        return " ".join(str(value).split())

    def _build_token_encoder(self) -> Any | None:
        """Create the tokenizer used for retrieval token budgeting."""

        if tiktoken is None:
            return None
        return tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        """Estimate the number of tokens in the provided text."""

        normalized = self._clean_text(text)
        if not normalized:
            return 0
        if self._encoding is None:
            return max(1, (len(normalized) + 3) // 4)
        return len(self._encoding.encode(normalized))

    def _truncate_to_token_budget(self, text: str, max_tokens: int) -> str:
        """Truncate text so it fits inside the remaining token budget."""

        normalized = self._clean_text(text)
        if max_tokens <= 0 or not normalized:
            return ""

        if self._encoding is None:
            max_chars = max_tokens * 4
            return normalized[:max_chars].rstrip()

        tokens = self._encoding.encode(normalized)
        if len(tokens) <= max_tokens:
            return normalized
        return self._encoding.decode(tokens[:max_tokens]).rstrip()

    def _embed_query(self, query: str) -> Sequence[float]:
        """Create an embedding for the rewritten search query."""

        try:
            response = self._openai_client.embeddings.create(
                model=self._settings.require_embedding_deployment(),
                input=query,
            )
        except Exception as exc:
            logger.exception("Failed to embed the rewritten query.")
            raise RAGError("Unable to embed the rewritten query.") from exc

        data = getattr(response, "data", [])
        if not data:
            raise RAGError("Embedding response did not include any vectors.")

        embedding = getattr(data[0], "embedding", None)
        if not embedding:
            raise RAGError("Embedding response did not include a vector.")
        return embedding

    @staticmethod
    def _build_search_client(settings: RagSettings) -> SearchClient:
        """Create an authenticated Azure AI Search client."""

        return SearchClient(
            endpoint=settings.require_search_endpoint(),
            index_name=settings.require_search_index_name(),
            credential=DefaultAzureCredential(),
        )

    @staticmethod
    def _coerce_mapping(result: Any) -> Mapping[str, Any]:
        """Coerce an SDK search result into a plain mapping."""

        if isinstance(result, Mapping):
            return result
        if hasattr(result, "items"):
            return dict(result.items())
        raise RAGError("Unexpected Azure AI Search result format.")
