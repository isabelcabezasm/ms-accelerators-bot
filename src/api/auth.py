"""JWT authentication helpers for FastAPI routes."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Annotated, Any, Final, cast

import httpx
import jwt
from cachetools import TTLCache
from fastapi import Depends, Header, HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from src.api.config import Settings
from src.api.dependencies import get_app_settings
from src.api.models import UserClaims

LOGGER = logging.getLogger(__name__)
AUTH_SCHEME: Final[str] = "Bearer"
_CACHE_MAXSIZE: Final[int] = 8
_JWKS_CACHE: TTLCache[str, dict[str, Any]] = TTLCache(
    maxsize=_CACHE_MAXSIZE,
    ttl=300,
)


def clear_jwks_cache() -> None:
    """Clear the in-memory JWKS cache used by token validation."""

    _JWKS_CACHE.clear()


def _unauthorized(detail: str) -> HTTPException:
    """Build a consistent 401 response for authentication failures."""

    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": AUTH_SCHEME},
    )


def _authentication_configuration_error() -> HTTPException:
    """Build a 500 response when auth settings are incomplete."""

    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication is not configured.",
    )


def extract_bearer_token(authorization_header: str | None) -> str:
    """Extract a bearer token from the Authorization header."""

    if authorization_header is None:
        raise _unauthorized("Missing Authorization header.")

    scheme, _, token = authorization_header.partition(" ")
    if scheme.casefold() != AUTH_SCHEME.casefold():
        raise _unauthorized("Invalid Authorization header.")

    stripped_token = token.strip()
    if not stripped_token:
        raise _unauthorized("Missing bearer token.")

    return stripped_token


def _cache_jwks_document(
    jwks_url: str,
    jwks_document: dict[str, Any],
    ttl_seconds: int,
) -> None:
    """Store the JWKS document in a TTL cache keyed by endpoint URL."""

    global _JWKS_CACHE

    if _JWKS_CACHE.ttl != ttl_seconds:
        _JWKS_CACHE = TTLCache(maxsize=_CACHE_MAXSIZE, ttl=ttl_seconds)
    _JWKS_CACHE[jwks_url] = jwks_document


def fetch_jwks_document(jwks_url: str, ttl_seconds: int) -> dict[str, Any]:
    """Fetch and cache the JWKS document used for signature validation."""

    cached_document = _JWKS_CACHE.get(jwks_url)
    if cached_document is not None:
        return cached_document

    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(jwks_url)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        LOGGER.exception("Failed to fetch JWKS document from %s", jwks_url)
        raise _unauthorized("Authentication service unavailable.") from exc

    jwks_payload = response.json()
    if not isinstance(jwks_payload, dict):
        LOGGER.error("Received malformed JWKS payload from %s", jwks_url)
        raise _unauthorized("Authentication service unavailable.")

    keys = jwks_payload.get("keys")
    if not isinstance(keys, list):
        LOGGER.error("Received malformed JWKS payload from %s", jwks_url)
        raise _unauthorized("Authentication service unavailable.")

    _cache_jwks_document(jwks_url, jwks_payload, ttl_seconds)
    jwks_document = jwks_payload
    return jwks_document


def _select_signing_key(
    jwks_document: Mapping[str, Any],
    key_id: str | None,
) -> Mapping[str, Any]:
    """Select the matching JWK entry for the token key identifier."""

    if not key_id:
        raise _unauthorized("Invalid access token.")

    for key in jwks_document.get("keys", []):
        if isinstance(key, dict) and key.get("kid") == key_id:
            return key

    LOGGER.warning("No signing key found for token kid %s", key_id)
    raise _unauthorized("Invalid access token.")


def _build_user_claims(token_claims: Mapping[str, Any]) -> UserClaims:
    """Map validated JWT claims into the typed user claims model."""

    email_claim = token_claims.get("email")
    if not isinstance(email_claim, str) or not email_claim:
        fallback_email = token_claims.get("preferred_username")
        if isinstance(fallback_email, str):
            email_claim = fallback_email
        else:
            email_claim = None

    name_claim = token_claims.get("name")
    if not isinstance(name_claim, str) or not name_claim:
        name_claim = None

    subject_claim = token_claims.get("sub")
    if not isinstance(subject_claim, str) or not subject_claim:
        raise _unauthorized("Invalid access token.")

    return UserClaims(
        sub=subject_claim,
        email=email_claim,
        name=name_claim,
    )


def validate_jwt_token(token: str, settings: Settings) -> UserClaims:
    """Validate a JWT against the configured issuer, audience, and JWKS."""

    try:
        audience = settings.require_azure_ad_client_id()
        issuer = settings.resolve_azure_ad_issuer()
        jwks_url = settings.resolve_azure_ad_jwks_url()
    except RuntimeError:
        LOGGER.exception("Azure AD authentication settings are incomplete.")
        raise _authentication_configuration_error() from None

    try:
        token_header = jwt.get_unverified_header(token)
    except InvalidTokenError as exc:
        LOGGER.warning("Failed to parse token header: %s", exc)
        raise _unauthorized("Invalid access token.") from exc

    algorithm = token_header.get("alg")
    if algorithm != "RS256":
        LOGGER.warning("Rejected unsupported JWT algorithm %s", algorithm)
        raise _unauthorized("Invalid access token.")

    jwks_document = fetch_jwks_document(
        jwks_url,
        settings.azure_ad_jwks_cache_ttl_seconds,
    )
    signing_key = _select_signing_key(jwks_document, token_header.get("kid"))

    try:
        public_key = cast(
            Any,
            RSAAlgorithm.from_jwk(json.dumps(signing_key)),
        )
        token_claims = jwt.decode(
            token,
            key=public_key,
            algorithms=["RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except ExpiredSignatureError as exc:
        LOGGER.info("Rejected expired JWT for issuer %s", issuer)
        raise _unauthorized("Access token has expired.") from exc
    except InvalidTokenError as exc:
        LOGGER.warning("JWT validation failed: %s", exc)
        raise _unauthorized("Invalid access token.") from exc

    return _build_user_claims(token_claims)


async def get_current_user(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UserClaims:
    """Resolve and validate the caller identity from the bearer token."""

    token = extract_bearer_token(authorization)
    return validate_jwt_token(token, settings)
