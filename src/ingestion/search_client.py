"""Azure AI Search helpers for the ingestion pipeline."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from azure.core.credentials import TokenCredential
from azure.core.exceptions import (
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.shared.models import AcceleratorChunk, AcceleratorDocument

SEARCH_HOST_SUFFIX = ".search.windows.net"
OPENAI_HOST_SUFFIX = ".openai.azure.com"


def validate_azure_endpoint(
    value: str | None,
    *,
    env_var: str,
    host_suffix: str,
) -> str:
    """Validate required Azure service endpoints before client creation."""

    if value is None:
        message = f"{env_var} must be configured."
        raise ValueError(message)

    endpoint = value.strip()
    if not endpoint or endpoint.lower() == "none":
        message = f"{env_var} must be configured."
        raise ValueError(message)

    parsed_endpoint = urlparse(endpoint)
    hostname = parsed_endpoint.hostname
    if parsed_endpoint.scheme != "https" or not hostname:
        message = f"{env_var} must be an https:// Azure endpoint."
        raise ValueError(message)

    normalized_host = hostname.lower()
    if not normalized_host.endswith(host_suffix):
        message = (
            f"{env_var} must match the Azure host pattern *{host_suffix}."
        )
        raise ValueError(message)

    return endpoint


@dataclass(frozen=True)
class ChangeDetectionResult:
    """Describe which documents changed since the last ingestion run."""

    changed_documents: list[AcceleratorDocument]
    skipped_documents: int


class SearchSettings(BaseSettings):
    """Load Azure AI Search settings from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ACCELERATORS_",
        extra="ignore",
    )

    search_endpoint: str | None = Field(default=None)
    search_index_name: str = Field(default="accelerators-index")
    semantic_configuration_name: str = Field(
        default="default-semantic-config"
    )
    embedding_dimensions: int = Field(default=3072, ge=1)
    upsert_batch_size: int = Field(default=100, ge=1, le=1000)
    retry_attempts: int = Field(default=3, ge=1, le=10)

    @field_validator("search_endpoint")
    @classmethod
    def validate_search_endpoint(cls, value: str | None) -> str:
        """Require a valid Azure AI Search endpoint URL."""

        return validate_azure_endpoint(
            value,
            env_var="ACCELERATORS_SEARCH_ENDPOINT",
            host_suffix=SEARCH_HOST_SUFFIX,
        )


class AcceleratorSearchClient:
    """Wrap Azure AI Search index management and document upserts."""

    def __init__(
        self,
        *,
        settings: SearchSettings | None = None,
        credential: TokenCredential | None = None,
        index_client: SearchIndexClient | Any | None = None,
        search_client: SearchClient | Any | None = None,
    ) -> None:
        """Create the search wrapper using managed identity by default."""

        self._settings = settings or SearchSettings()
        self._credential = credential or DefaultAzureCredential()

        if index_client is not None and search_client is not None:
            self._index_client = index_client
            self._search_client = search_client
            return

        endpoint = validate_azure_endpoint(
            self._settings.search_endpoint,
            env_var="ACCELERATORS_SEARCH_ENDPOINT",
            host_suffix=SEARCH_HOST_SUFFIX,
        )

        self._index_client = index_client or SearchIndexClient(
            endpoint=endpoint,
            credential=self._credential,
        )
        self._search_client = search_client or SearchClient(
            endpoint=endpoint,
            index_name=self._settings.search_index_name,
            credential=self._credential,
        )

    @property
    def index_name(self) -> str:
        """Return the configured Azure AI Search index name."""

        return self._settings.search_index_name

    def build_index_definition(self) -> dict[str, Any]:
        """Return the hybrid index schema required by the PRD."""

        return {
            "name": self._settings.search_index_name,
            "fields": [
                {
                    "name": "id",
                    "type": "Edm.String",
                    "key": True,
                    "filterable": True,
                    "sortable": True,
                    "analyzer": "keyword",
                },
                {
                    "name": "parent_id",
                    "type": "Edm.String",
                    "filterable": True,
                    "sortable": True,
                    "retrievable": True,
                },
                {
                    "name": "chunk_id",
                    "type": "Edm.String",
                    "filterable": True,
                    "sortable": True,
                    "retrievable": True,
                },
                {
                    "name": "name",
                    "type": "Edm.String",
                    "searchable": True,
                    "retrievable": True,
                    "sortable": True,
                },
                {
                    "name": "summary",
                    "type": "Edm.String",
                    "searchable": True,
                    "retrievable": True,
                },
                {
                    "name": "long_description",
                    "type": "Edm.String",
                    "searchable": True,
                    "retrievable": True,
                    "analyzer": "en.microsoft",
                },
                {
                    "name": "categories",
                    "type": "Collection(Edm.String)",
                    "searchable": True,
                    "retrievable": True,
                    "filterable": True,
                    "facetable": True,
                },
                {
                    "name": "industries",
                    "type": "Collection(Edm.String)",
                    "searchable": True,
                    "retrievable": True,
                    "filterable": True,
                    "facetable": True,
                },
                {
                    "name": "azure_services",
                    "type": "Collection(Edm.String)",
                    "searchable": True,
                    "retrievable": True,
                    "filterable": True,
                    "facetable": True,
                },
                {
                    "name": "languages",
                    "type": "Collection(Edm.String)",
                    "searchable": True,
                    "retrievable": True,
                    "filterable": True,
                    "facetable": True,
                },
                {
                    "name": "deployment",
                    "type": "Collection(Edm.String)",
                    "searchable": True,
                    "retrievable": True,
                    "filterable": True,
                    "facetable": True,
                },
                {
                    "name": "url",
                    "type": "Edm.String",
                    "retrievable": True,
                },
                {
                    "name": "github_url",
                    "type": "Edm.String",
                    "retrievable": True,
                },
                {
                    "name": "last_updated",
                    "type": "Edm.DateTimeOffset",
                    "retrievable": True,
                    "filterable": True,
                    "sortable": True,
                },
                {
                    "name": "stars",
                    "type": "Edm.Int32",
                    "retrievable": True,
                    "filterable": True,
                    "sortable": True,
                },
                {
                    "name": "content_hash",
                    "type": "Edm.String",
                    "retrievable": True,
                    "filterable": True,
                },
                {
                    "name": "content_vector",
                    "type": "Collection(Edm.Single)",
                    "searchable": True,
                    "retrievable": False,
                    "stored": False,
                    "dimensions": self._settings.embedding_dimensions,
                    "vectorSearchProfile": "default-vector-profile",
                },
            ],
            "vectorSearch": {
                "algorithms": [
                    {
                        "name": "default-hnsw",
                        "kind": "hnsw",
                        "hnswParameters": {
                            "m": 4,
                            "efConstruction": 400,
                            "efSearch": 100,
                            "metric": "cosine",
                        },
                    }
                ],
                "profiles": [
                    {
                        "name": "default-vector-profile",
                        "algorithm": "default-hnsw",
                    }
                ],
            },
            "semantic": {
                "configurations": [
                    {
                        "name": self._settings.semantic_configuration_name,
                        "prioritizedFields": {
                            "titleField": {"fieldName": "name"},
                            "prioritizedContentFields": [
                                {"fieldName": "long_description"},
                                {"fieldName": "summary"},
                            ],
                            "prioritizedKeywordsFields": [
                                {"fieldName": "categories"},
                                {"fieldName": "azure_services"},
                            ],
                        },
                    }
                ]
            },
        }

    def ensure_index(self) -> None:
        """Create or update the Azure AI Search index schema."""

        self._index_client.create_or_update_index(
            self.build_index_definition(),
            allow_index_downtime=True,
        )

    def detect_changes(
        self,
        documents: Sequence[AcceleratorDocument],
    ) -> ChangeDetectionResult:
        """Return only documents whose content hash changed."""

        if not documents:
            return ChangeDetectionResult([], 0)

        existing_hashes = self._get_existing_hashes(
            [document.id for document in documents]
        )
        changed_documents = [
            document
            for document in documents
            if existing_hashes.get(document.id) != document.content_hash
        ]
        skipped_documents = len(documents) - len(changed_documents)
        return ChangeDetectionResult(changed_documents, skipped_documents)

    def upsert_chunks(self, chunks: Sequence[AcceleratorChunk]) -> None:
        """Merge-or-upload chunk documents with retry handling."""

        documents = [chunk.to_search_document() for chunk in chunks]
        for batch in _batched(documents, self._settings.upsert_batch_size):
            self._upsert_batch(batch)

    def _get_existing_hashes(
        self,
        parent_ids: Sequence[str],
    ) -> dict[str, str]:
        """Fetch the stored content hash for each known parent document."""

        hashes: dict[str, str] = {}
        for parent_id in parent_ids:
            filter_expression = _build_parent_filter(parent_id)
            try:
                results = self._search_client.search(
                    search_text="*",
                    filter=filter_expression,
                    top=1,
                    select=["parent_id", "content_hash"],
                )
            except ResourceNotFoundError:
                return {}

            for result in results:
                row = _coerce_mapping(result)
                result_parent_id = row.get("parent_id")
                result_hash = row.get("content_hash")
                if isinstance(result_parent_id, str) and isinstance(
                    result_hash, str
                ):
                    hashes[result_parent_id] = result_hash
                break
        return hashes

    def _upsert_batch(self, batch: list[dict[str, Any]]) -> None:
        """Upload a single batch and retry transient Azure SDK failures."""

        last_error: Exception | None = None
        for attempt in range(1, self._settings.retry_attempts + 1):
            try:
                results = self._search_client.merge_or_upload_documents(batch)
            except (HttpResponseError, ServiceRequestError) as error:
                last_error = error
                if attempt == self._settings.retry_attempts:
                    raise
                time.sleep(2 ** (attempt - 1))
                continue

            failed_keys = [
                _extract_result_key(result)
                for result in results
                if not _result_succeeded(result)
            ]
            if failed_keys:
                joined_keys = ", ".join(sorted(failed_keys))
                message = f"Failed to upsert search documents: {joined_keys}"
                raise RuntimeError(message)
            return

        if last_error is not None:
            raise last_error


def _batched(
    items: Sequence[dict[str, Any]],
    batch_size: int,
) -> Iterable[list[dict[str, Any]]]:
    """Yield sequential slices of documents for Search batch uploads."""

    for index in range(0, len(items), batch_size):
        yield list(items[index : index + batch_size])



def _build_parent_filter(parent_id: str) -> str:
    """Escape a parent identifier for a Search filter expression."""

    escaped_parent_id = parent_id.replace("'", "''")
    return f"parent_id eq '{escaped_parent_id}'"



def _coerce_mapping(result: Any) -> Mapping[str, Any]:
    """Normalize Azure SDK result shapes for easier testing."""

    if isinstance(result, Mapping):
        return result
    if hasattr(result, "__getitem__"):
        return {
            "parent_id": result["parent_id"],
            "content_hash": result["content_hash"],
        }
    message = "Azure AI Search returned an unsupported result payload."
    raise TypeError(message)



def _result_succeeded(result: Any) -> bool:
    """Return whether an Azure indexing result indicates success."""

    if isinstance(result, Mapping):
        return bool(result.get("succeeded", False))
    return bool(getattr(result, "succeeded", False))



def _extract_result_key(result: Any) -> str:
    """Return the indexing result key for logging and exceptions."""

    if isinstance(result, Mapping):
        return str(result.get("key", "<unknown>"))
    return str(getattr(result, "key", "<unknown>"))
