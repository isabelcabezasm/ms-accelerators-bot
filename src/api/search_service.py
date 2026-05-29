"""Azure AI Search service for the FastAPI search endpoint."""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any

from azure.core.credentials import TokenCredential
from azure.core.exceptions import HttpResponseError, ServiceRequestError
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.models import (
    QueryCaptionType,
    QueryType,
    VectorizedQuery,
)
from openai import AzureOpenAI
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.api.models import SearchResult
from src.ingestion.search_client import (
    OPENAI_HOST_SUFFIX,
    SEARCH_HOST_SUFFIX,
    validate_azure_endpoint,
)

logger = logging.getLogger(__name__)


class SearchServiceError(RuntimeError):
    """Raise when the backing Azure services cannot complete a query."""


class SearchServiceSettings(BaseSettings):
    """Load Azure AI Search and embedding settings from the environment."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    search_endpoint: str | None = Field(
        default=None,
        alias="AZURE_SEARCH_ENDPOINT",
    )
    search_index_name: str = Field(
        default="accelerators-index",
        alias="AZURE_SEARCH_INDEX_NAME",
    )
    openai_endpoint: str | None = Field(
        default=None,
        alias="AZURE_OPENAI_ENDPOINT",
    )
    openai_embedding_deployment: str = Field(
        alias="AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
        min_length=1,
    )
    openai_api_version: str = Field(
        default="2024-10-21",
        alias="AZURE_OPENAI_API_VERSION",
    )
    semantic_configuration_name: str = Field(
        default="default-semantic-config",
        alias="AZURE_SEARCH_SEMANTIC_CONFIGURATION",
    )
    vector_field_name: str = Field(default="content_vector")

    @field_validator("search_endpoint")
    @classmethod
    def validate_search_endpoint(cls, value: str | None) -> str:
        """Require a valid Azure AI Search endpoint URL."""

        return validate_azure_endpoint(
            value,
            env_var="AZURE_SEARCH_ENDPOINT",
            host_suffix=SEARCH_HOST_SUFFIX,
        )

    @field_validator("openai_endpoint")
    @classmethod
    def validate_openai_endpoint(cls, value: str | None) -> str:
        """Require a valid Azure OpenAI endpoint URL."""

        return validate_azure_endpoint(
            value,
            env_var="AZURE_OPENAI_ENDPOINT",
            host_suffix=OPENAI_HOST_SUFFIX,
        )


class SearchService:
    """Execute hybrid Azure AI Search queries with semantic reranking."""

    def __init__(
        self,
        *,
        settings: SearchServiceSettings | None = None,
        credential: TokenCredential | None = None,
        search_client: SearchClient | Any | None = None,
        openai_client: AzureOpenAI | Any | None = None,
    ) -> None:
        """Create the service with managed-identity Azure SDK clients."""

        self._settings = settings or SearchServiceSettings()
        self._credential = credential
        self._search_client = search_client
        self._openai_client = openai_client

    def search(self, query: str, top: int) -> list[SearchResult]:
        """Run a hybrid BM25 plus vector query and map ranked results."""

        search_text = query.strip()
        if not search_text:
            raise ValueError("The search query must not be empty.")

        logger.info("Executing hybrid search", extra={"top": top})
        vector_query = VectorizedQuery(
            vector=self._embed_query(search_text),
            fields=self._settings.vector_field_name,
            k_nearest_neighbors=max(top * 3, top),
        )
        try:
            results = self._get_search_client().search(
                search_text=search_text,
                semantic_query=search_text,
                query_type=QueryType.SEMANTIC,
                semantic_configuration_name=(
                    self._settings.semantic_configuration_name
                ),
                query_caption=QueryCaptionType.EXTRACTIVE,
                query_caption_highlight_enabled=False,
                vector_queries=[vector_query],
                select=[
                    "parent_id",
                    "name",
                    "summary",
                    "long_description",
                    "url",
                ],
                top=top,
            )
        except (HttpResponseError, ServiceRequestError) as error:
            logger.exception("Azure AI Search query failed")
            raise SearchServiceError(
                "Azure AI Search query failed."
            ) from error

        return self._collapse_results(results, limit=top)

    def _embed_query(self, query: str) -> list[float]:
        """Embed the incoming search query with Azure OpenAI."""

        try:
            response = self._get_openai_client().embeddings.create(
                model=self._settings.openai_embedding_deployment,
                input=[query],
            )
        except Exception as error:  # pragma: no cover - SDK errors vary.
            logger.exception("Azure OpenAI embedding request failed")
            raise SearchServiceError(
                "Azure OpenAI embedding request failed."
            ) from error

        return list(response.data[0].embedding)

    def _collapse_results(
        self,
        results: Sequence[Mapping[str, Any]] | Any,
        *,
        limit: int,
    ) -> list[SearchResult]:
        """Collapse chunk matches into unique ranked accelerator results."""

        ranked_results: list[SearchResult] = []
        seen_keys: set[str] = set()
        for raw_result in results:
            row = dict(raw_result)
            unique_key = self._build_unique_key(row)
            if unique_key in seen_keys:
                continue
            seen_keys.add(unique_key)
            ranked_results.append(
                SearchResult(
                    title=str(row.get("name", "")),
                    description=self._select_description(row),
                    score=self._extract_score(row),
                    url=str(row.get("url", "")),
                )
            )
            if len(ranked_results) >= limit:
                break
        return ranked_results

    def _build_unique_key(self, row: Mapping[str, Any]) -> str:
        """Choose a stable key so duplicate chunks collapse cleanly."""

        for field_name in ("parent_id", "url", "name"):
            value = row.get(field_name)
            if isinstance(value, str) and value:
                return value
        return repr(sorted(row.items()))

    def _select_description(self, row: Mapping[str, Any]) -> str:
        """Prefer semantic captions, then summary, then long description."""

        captions = row.get("@search.captions")
        if isinstance(captions, Sequence) and not isinstance(
            captions,
            (str, bytes),
        ):
            for caption in captions:
                if isinstance(caption, Mapping):
                    text = caption.get("text")
                    if isinstance(text, str) and text.strip():
                        return text.strip()
        for field_name in ("summary", "long_description"):
            value = row.get(field_name)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _extract_score(self, row: Mapping[str, Any]) -> float:
        """Prefer the semantic reranker score when it is available."""

        for field_name in ("@search.reranker_score", "@search.score"):
            value = row.get(field_name)
            if isinstance(value, (int, float)):
                return float(value)
        return 0.0

    def _get_search_client(self) -> SearchClient:
        """Create the Azure AI Search client lazily for testability."""

        if self._search_client is None:
            self._search_client = SearchClient(
                endpoint=self._settings.search_endpoint,
                index_name=self._settings.search_index_name,
                credential=self._get_credential(),
            )
        return self._search_client

    def _get_openai_client(self) -> AzureOpenAI | Any:
        """Create the Azure OpenAI client lazily for testability."""

        if self._openai_client is None:
            token_provider = get_bearer_token_provider(
                self._get_credential(),
                "https://cognitiveservices.azure.com/.default",
            )
            self._openai_client = AzureOpenAI(
                azure_endpoint=self._settings.openai_endpoint,
                api_version=self._settings.openai_api_version,
                azure_ad_token_provider=token_provider,
            )
        return self._openai_client

    def _get_credential(self) -> TokenCredential:
        """Create and cache the managed identity credential on demand."""

        if self._credential is None:
            self._credential = DefaultAzureCredential()
        return self._credential
