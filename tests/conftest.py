"""Shared pytest fixtures for backend tests."""

from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from src.api.main import app


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Provide a test client for exercising the FastAPI app."""

    with TestClient(app) as test_client:
        yield test_client
