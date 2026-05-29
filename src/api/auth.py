"""JWT authentication helpers for FastAPI routes."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Annotated, Any, Final, cast
from urllib.parse import urlparse

import httpx
import jwt
from fastapi import Depends, Header, HTTPException, status
from jwt import ExpiredSignatureError, InvalidTokenError
from jwt.algorithms import RSAAlgorithm

from src.api.config import Settings
from src.api.dependencies import get_app_settings
from src.api.models import UserClaims

LOGGER = logging.getLogger(__name__)
AUTH_SCHEME: Final[str] = "Bearer"
_TRUSTED_AZURE_AD_HOSTS: Final[frozenset[str]] = frozenset(
    {
        "login.microsoftonline.com",
        "login.microsoftonline.us",
        "login.microsoftonline.de",
        "login.chinacloudapi.cn",
    }
)


@dataclass(slots=True)
class _CachedJwksDocument:
    """Store a JWKS payload together with its monotonic expiry time."""

    document: dict[str, Any]
    expires_at: float


_JWKS_CACHE: dict[str, _CachedJwksDocument] = {}
_JWKS_CACHE_LOCK: Final[RLock] = RLock()


def clear_jwks_cache() -> None:
    """Clear the in-memory JWKS cache used by token validation."""

    with _JWKS_CACHE_LOCK:
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


def _build_azure_ad_jwks_url(issuer: str) -> str:
    """Build a trusted Microsoft JWKS URL from the configured issuer."""

    parsed_issuer = urlparse(issuer)
    hostname = parsed_issuer.hostname
    normalized_host = hostname.lower() if hostname else None
    if (
        parsed_issuer.scheme != "https"
        or normalized_host is None
        or normalized_host not in _TRUSTED_AZURE_AD_HOSTS
        or parsed_issuer.username is not None
        or parsed_issuer.password is not None
        or parsed_issuer.port is not None
    ):
        raise RuntimeError("AZURE_AD_ISSUER must use a trusted Azure AD URL.")

    path_segments = [
        segment for segment in parsed_issuer.path.split("/") if segment
    ]
    if not path_segments:
        raise RuntimeError("AZURE_AD_ISSUER must include an Azure tenant.")

    if len(path_segments) > 2:
        raise RuntimeError("AZURE_AD_ISSUER has an unsupported path.")

    if len(path_segments) == 2 and path_segments[1] != "v2.0":
        raise RuntimeError("AZURE_AD_ISSUER has an unsupported path.")

    tenant = path_segments[0]
    return (
        f"{parsed_issuer.scheme}://{normalized_host}/{tenant}"
        "/discovery/v2.0/keys"
    )


def _get_cached_jwks_document(jwks_url: str) -> dict[str, Any] | None:
    """Return a cached JWKS document when the entry is still fresh."""

    cached_entry = _JWKS_CACHE.get(jwks_url)
    if cached_entry is None:
        return None

    if cached_entry.expires_at <= monotonic():
        _JWKS_CACHE.pop(jwks_url, None)
        return None

    return cached_entry.document


def _cache_jwks_document(
    jwks_url: str,
    jwks_document: dict[str, Any],
    ttl_seconds: int,
) -> None:
    """Store the JWKS document with a per-entry expiry."""

    _JWKS_CACHE[jwks_url] = _CachedJwksDocument(
        document=jwks_document,
        expires_at=monotonic() + ttl_seconds,
    )


def _fetch_jwks_document_from_remote(jwks_url: str) -> dict[str, Any]:
    """Fetch a JWKS document from the trusted Azure AD endpoint."""

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

    return jwks_payload


def fetch_jwks_document(jwks_url: str, ttl_seconds: int) -> dict[str, Any]:
    """Fetch and cache the JWKS document used for signature validation."""

    with _JWKS_CACHE_LOCK:
        cached_document = _get_cached_jwks_document(jwks_url)
        if cached_document is not None:
            return cached_document

        jwks_document = _fetch_jwks_document_from_remote(jwks_url)
        _cache_jwks_document(jwks_url, jwks_document, ttl_seconds)
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
        jwks_url = _build_azure_ad_jwks_url(issuer)
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


def get_current_user(
    settings: Annotated[Settings, Depends(get_app_settings)],
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> UserClaims:
    """Resolve and validate the caller identity from the bearer token."""

    token = extract_bearer_token(authorization)
    return validate_jwt_token(token, settings)
