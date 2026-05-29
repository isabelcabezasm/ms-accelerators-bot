"""Configuration settings for the FastAPI application."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Load API settings from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="ACCELERATORS_",
        extra="ignore",
    )

    app_name: str = Field(default="Microsoft Accelerators Finder API")
    app_version: str = Field(default="0.1.0")
    environment: str = Field(default="development")


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object for dependency injection."""

    return Settings()
