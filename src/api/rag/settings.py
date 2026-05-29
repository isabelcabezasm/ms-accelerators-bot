"""Configuration helpers for the chat RAG pipeline."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.ingestion.search_client import (
    OPENAI_HOST_SUFFIX,
    SEARCH_HOST_SUFFIX,
    validate_azure_endpoint,
)


class RagSettings(BaseSettings):
    """Configuration values for the retrieval augmented generation flow."""
    """Stores Azure settings needed by the RAG components."""

    model_config = SettingsConfigDict(
        env_prefix="ACCELERATORS_",
        extra="ignore",
        populate_by_name=True,
    )

    azure_openai_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AZURE_OPENAI_ENDPOINT",
            "ACCELERATORS_AZURE_OPENAI_ENDPOINT",
            "ACCELERATORS_OPENAI_ENDPOINT",
        ),
    )
    azure_openai_chat_deployment: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AZURE_OPENAI_CHAT_DEPLOYMENT",
            "ACCELERATORS_AZURE_OPENAI_CHAT_DEPLOYMENT",
            "ACCELERATORS_OPENAI_CHAT_DEPLOYMENT",
        ),
    )
    azure_openai_embedding_deployment: str = Field(
        default="text-embedding-3-large",
        validation_alias=AliasChoices(
            "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "ACCELERATORS_AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
            "ACCELERATORS_OPENAI_EMBEDDING_DEPLOYMENT",
        ),
    )
    azure_openai_api_version: str = Field(
        default="2024-10-21",
        validation_alias=AliasChoices(
            "AZURE_OPENAI_API_VERSION",
            "ACCELERATORS_AZURE_OPENAI_API_VERSION",
            "ACCELERATORS_OPENAI_API_VERSION",
        ),
    )
    azure_search_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AZURE_SEARCH_ENDPOINT",
            "ACCELERATORS_AZURE_SEARCH_ENDPOINT",
            "ACCELERATORS_SEARCH_ENDPOINT",
        ),
    )
    azure_search_index_name: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "AZURE_SEARCH_INDEX_NAME",
            "ACCELERATORS_AZURE_SEARCH_INDEX_NAME",
            "ACCELERATORS_SEARCH_INDEX_NAME",
        ),
    )
    semantic_configuration_name: str = Field(
        default="default-semantic-config"
    )
    top_k: int = Field(default=8, ge=1, le=20)
    rewrite_max_tokens: int = Field(default=128, ge=32, le=512)
    context_token_budget: int = Field(default=2500, ge=256, le=12000)
    answer_max_tokens: int = Field(default=600, ge=128, le=2048)
    trusted_citation_domains: tuple[str, ...] = Field(
        default=("accelerators.ms", "github.com")
    )

    def require_openai_endpoint(self) -> str:
        """Return a validated Azure OpenAI endpoint."""

        endpoint = self.azure_openai_endpoint
        if not endpoint:
            raise ValueError("Azure OpenAI endpoint is not configured.")
        return validate_azure_endpoint(endpoint, OPENAI_HOST_SUFFIX)

    def require_chat_deployment(self) -> str:
        """Return the configured chat deployment name."""

        deployment = self.azure_openai_chat_deployment
        if not deployment:
            raise ValueError("Azure OpenAI chat deployment is not configured.")
        return deployment

    def require_embedding_deployment(self) -> str:
        """Return the configured embedding deployment name."""

        deployment = self.azure_openai_embedding_deployment
        if not deployment:
            raise ValueError(
                "Azure OpenAI embedding deployment is not configured."
            )
        return deployment

    def require_search_endpoint(self) -> str:
        """Return a validated Azure AI Search endpoint."""

        endpoint = self.azure_search_endpoint
        if not endpoint:
            raise ValueError("Azure AI Search endpoint is not configured.")
        return validate_azure_endpoint(endpoint, SEARCH_HOST_SUFFIX)

    def require_search_index_name(self) -> str:
        """Return the configured Azure AI Search index name."""

        index_name = self.azure_search_index_name
        if not index_name:
            raise ValueError("Azure AI Search index name is not configured.")
        return index_name
    answer_max_tokens: int = Field(default=600, ge=128, le=2048)

    def require_openai_endpoint(self) -> str:
        """Returns a validated Azure OpenAI endpoint."""

        return validate_azure_endpoint(
            self.azure_openai_endpoint,
            expected_host_suffix=OPENAI_HOST_SUFFIX,
            variable_name="AZURE_OPENAI_ENDPOINT",
        )

    def require_chat_deployment(self) -> str:
        """Returns the configured chat deployment name."""

        if not self.azure_openai_chat_deployment:
            msg = "AZURE_OPENAI_CHAT_DEPLOYMENT must be configured."
            raise ValueError(msg)
        return self.azure_openai_chat_deployment

    def require_embedding_deployment(self) -> str:
        """Returns the configured embedding deployment name."""

        if not self.azure_openai_embedding_deployment:
            msg = "AZURE_OPENAI_EMBEDDING_DEPLOYMENT must be configured."
            raise ValueError(msg)
        return self.azure_openai_embedding_deployment

    def require_search_endpoint(self) -> str:
        """Returns a validated Azure AI Search endpoint."""

        return validate_azure_endpoint(
            self.azure_search_endpoint,
            expected_host_suffix=SEARCH_HOST_SUFFIX,
            variable_name="AZURE_SEARCH_ENDPOINT",
        )

    def require_search_index_name(self) -> str:
        """Returns the configured AI Search index name."""

        if not self.azure_search_index_name:
            msg = "AZURE_SEARCH_INDEX_NAME must be configured."
            raise ValueError(msg)
        return self.azure_search_index_name


@lru_cache(maxsize=1)
def get_rag_settings() -> RagSettings:
    """Return the cached RAG settings instance."""
    """Returns a cached settings instance for the RAG pipeline."""

    return RagSettings()
