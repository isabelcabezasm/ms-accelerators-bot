"""Tests for the FastAPI health endpoint."""

from fastapi.testclient import TestClient


def test_healthz_returns_ok(client: TestClient) -> None:
    """Verify the health endpoint returns a successful status payload."""

    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
