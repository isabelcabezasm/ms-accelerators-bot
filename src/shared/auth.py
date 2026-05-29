"""Shared authentication helpers and token validation placeholders."""

from dataclasses import dataclass
from typing import Final

AUTH_SCHEME: Final[str] = "Bearer"


@dataclass(slots=True)
class AuthContext:
    """Represent the authenticated user context for API handlers."""

    user_id: str
    roles: tuple[str, ...] = ()


def extract_bearer_token(
    authorization_header: str | None,
) -> str | None:
    """Extract a bearer token from an Authorization header."""

    if authorization_header is None:
        return None

    scheme, _, token = authorization_header.partition(" ")
    if scheme.casefold() != AUTH_SCHEME.casefold():
        return None

    stripped_token = token.strip()
    if not stripped_token:
        return None

    return stripped_token


def validate_access_token(token: str) -> AuthContext:
    """Validate an access token once Entra wiring is implemented."""

    raise NotImplementedError(
        "Token validation is not wired yet. Replace this scaffold with "
        "Microsoft Entra External ID JWT validation."
    )
