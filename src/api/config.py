"""Configuration settings for the FastAPI application."""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load API settings from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ACCELERATORS_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = Field(default="Microsoft Accelerators Finder API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")
    applicationinsights_connection_string: str | None = Field(
        default=None,
        alias="APPLICATIONINSIGHTS_CONNECTION_STRING",
    )
    azure_ad_tenant_id: str | None = Field(
        validation_alias=AliasChoices(
            "AZURE_AD_TENANT_ID",
            "ACCELERATORS_AZURE_AD_TENANT_ID",
        ),
    )
    azure_ad_client_id: str | None = Field(
            "AZURE_AD_CLIENT_ID",
            "ACCELERATORS_AZURE_AD_CLIENT_ID",
    )
    azure_ad_issuer: str | None = Field(
            "AZURE_AD_ISSUER",
            "ACCELERATORS_AZURE_AD_ISSUER",
    )
    azure_ad_jwks_cache_ttl_seconds: int = Field(default=300, ge=1)

    def require_azure_ad_client_id(self) -> str:
        """Return the configured Azure AD audience or raise an error."""

        if self.azure_ad_client_id:
            return self.azure_ad_client_id

        raise RuntimeError("AZURE_AD_CLIENT_ID must be configured.")

    def resolve_azure_ad_issuer(self) -> str:
        """Resolve the expected Azure AD issuer for JWT validation."""

        if self.azure_ad_issuer:
            return self.azure_ad_issuer.rstrip("/")

        if self.azure_ad_tenant_id:
            return (
                "https://login.microsoftonline.com/"
                f"{self.azure_ad_tenant_id}/v2.0"
            )

        raise RuntimeError(
            "Configure AZURE_AD_ISSUER or AZURE_AD_TENANT_ID for auth."
        )

    def resolve_azure_ad_jwks_url(self) -> str:
        """Build the JWKS endpoint used to validate JWT signatures."""

        issuer = self.resolve_azure_ad_issuer()
        return f"{issuer}/discovery/v2.0/keys"
            "APPLICATIONINSIGHTS_CONNECTION_STRING",
            "ACCELERATORS_APPLICATIONINSIGHTS_CONNECTION_STRING",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object for dependency injection."""

    return Settings()
