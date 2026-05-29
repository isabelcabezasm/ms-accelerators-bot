"""Tests for JWT authentication helpers and dependencies."""

from __future__ import annotations

import base64
from collections.abc import Generator
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from src.api.auth import clear_jwks_cache, get_current_user
from src.api.config import get_settings
from src.api.models import UserClaims

TENANT_ID = "test-tenant-id"
CLIENT_ID = "test-client-id"
ISSUER = f"https://login.microsoftonline.com/{TENANT_ID}/v2.0"
JWKS_URL = (
    f"https://login.microsoftonline.com/{TENANT_ID}/discovery/v2.0/keys"
)
KEY_ID = "test-key-id"


class MockResponse:
    """Minimal HTTP response double for mocked JWKS requests."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Store the mocked JSON payload returned to the auth code."""

        self._payload = payload

    def raise_for_status(self) -> None:
        """Pretend the mocked response completed successfully."""

    def json(self) -> dict[str, Any]:
        """Return the mocked JWKS payload for the test request."""

        return self._payload


class MockHttpxClient:
    """Context-managed HTTP client double for JWKS fetches."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Store the JWKS payload returned for each mocked request."""

        self._payload = payload

    def __enter__(self) -> MockHttpxClient:
        """Return the client instance when entering the context."""

        return self

    def __exit__(self, *args: object) -> None:
        """Allow the mocked client to be used as a context manager."""

    def get(self, url: str) -> MockResponse:
        """Return the JWKS payload for the expected endpoint URL."""

        assert url == JWKS_URL
        return MockResponse(self._payload)


@pytest.fixture(autouse=True)
def reset_auth_state(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[None, None, None]:
    """Reset cached settings and auth state between tests."""

    monkeypatch.setenv("AZURE_AD_TENANT_ID", TENANT_ID)
    monkeypatch.setenv("AZURE_AD_CLIENT_ID", CLIENT_ID)
    monkeypatch.delenv("AZURE_AD_ISSUER", raising=False)
    get_settings.cache_clear()
    clear_jwks_cache()
    yield
    get_settings.cache_clear()
    clear_jwks_cache()


@pytest.fixture
def app() -> FastAPI:
    """Build a small FastAPI app that protects a single route."""

    test_app = FastAPI()

    @test_app.get("/me", response_model=UserClaims)
    async def read_current_user(
        user: Annotated[UserClaims, Depends(get_current_user)],
    ) -> UserClaims:
        """Return the authenticated user claims for test assertions."""

        return user

    return test_app


@pytest.fixture
def rsa_private_key() -> rsa.RSAPrivateKey:
    """Generate an RSA private key for signing test access tokens."""

    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _base64url_uint(value: int) -> str:
    """Encode an RSA integer using the JWK base64url format."""

    byte_length = max(1, (value.bit_length() + 7) // 8)
    encoded = base64.urlsafe_b64encode(value.to_bytes(byte_length, "big"))
    return encoded.rstrip(b"=").decode("ascii")


def _build_jwks(private_key: rsa.RSAPrivateKey) -> dict[str, Any]:
    """Build a JWKS payload matching the generated RSA key pair."""

    public_numbers = private_key.public_key().public_numbers()
    return {
        "keys": [
            {
                "kty": "RSA",
                "use": "sig",
                "kid": KEY_ID,
                "alg": "RS256",
                "n": _base64url_uint(public_numbers.n),
                "e": _base64url_uint(public_numbers.e),
            }
        ]
    }


def _build_token(
    private_key: rsa.RSAPrivateKey,
    *,
    expires_delta: timedelta,
) -> str:
    """Create a signed JWT with the claims expected by the dependency."""

    now = datetime.now(UTC)
    payload = {
        "sub": "user-123",
        "email": "joey@example.com",
        "name": "Joey Backend",
        "iss": ISSUER,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": KEY_ID},
    )


def _mock_jwks_request(
    monkeypatch: pytest.MonkeyPatch,
    jwks_payload: dict[str, Any],
) -> None:
    """Mock the JWKS HTTP request issued by the auth dependency."""

    def build_client(*args: object, **kwargs: object) -> MockHttpxClient:
        """Return a context-managed JWKS client double."""

        del args, kwargs
        return MockHttpxClient(jwks_payload)

    monkeypatch.setattr("src.api.auth.httpx.Client", build_client)


def test_get_current_user_returns_claims(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
) -> None:
    """Return user claims when the bearer token is valid."""

    _mock_jwks_request(monkeypatch, _build_jwks(rsa_private_key))
    token = _build_token(rsa_private_key, expires_delta=timedelta(minutes=5))

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {
        "sub": "user-123",
        "email": "joey@example.com",
        "name": "Joey Backend",
    }


def test_get_current_user_rejects_expired_token(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
) -> None:
    """Reject expired JWTs with a 401 response."""

    _mock_jwks_request(monkeypatch, _build_jwks(rsa_private_key))
    token = _build_token(rsa_private_key, expires_delta=timedelta(minutes=-5))

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 401
    assert response.json() == {"detail": "Access token has expired."}


def test_get_current_user_rejects_missing_header(app: FastAPI) -> None:
    """Reject requests that do not include an Authorization header."""

    client = TestClient(app)
    response = client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "Missing Authorization header."}


def test_get_current_user_rejects_malformed_token(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
    rsa_private_key: rsa.RSAPrivateKey,
) -> None:
    """Reject malformed bearer tokens before claims are returned."""

    _mock_jwks_request(monkeypatch, _build_jwks(rsa_private_key))

    client = TestClient(app)
    response = client.get(
        "/me",
        headers={"Authorization": "Bearer not-a-valid-jwt"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token."}


def test_get_current_user_rejects_untrusted_jwks_url(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject issuers that would derive a non-Microsoft JWKS URL."""

    monkeypatch.setenv(
        "AZURE_AD_ISSUER",
        f"https://evil.example.com/{TENANT_ID}/v2.0",
    )
    get_settings.cache_clear()

    def build_client(*args: object, **kwargs: object) -> MockHttpxClient:
        """Fail the test if auth attempts to fetch an untrusted JWKS URL."""

        del args, kwargs
        raise AssertionError(
            "JWKS fetch should not run for untrusted issuers."
        )

    monkeypatch.setattr("src.api.auth.httpx.Client", build_client)

    client = TestClient(app)
    response = client.get("/me", headers={"Authorization": "Bearer any"})

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Authentication is not configured.",
    }


def test_get_current_user_rejects_non_rs256_tokens(
    app: FastAPI,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject tokens that do not use the pinned RS256 algorithm."""

    token = jwt.encode(
        {
            "sub": "user-123",
            "email": "joey@example.com",
            "name": "Joey Backend",
            "iss": ISSUER,
            "aud": CLIENT_ID,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        "shared-secret-for-hs256-regression-checks",
        algorithm="HS256",
        headers={"kid": KEY_ID},
    )

    def build_client(*args: object, **kwargs: object) -> MockHttpxClient:
        """Fail the test if a non-RS256 token reaches JWKS fetching."""

        del args, kwargs
        raise AssertionError(
            "JWKS fetch should not run for HS256 tokens."
        )

    monkeypatch.setattr("src.api.auth.httpx.Client", build_client)

    client = TestClient(app)
    response = client.get(
        "/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 401
    assert response.json() == {"detail": "Invalid access token."}
