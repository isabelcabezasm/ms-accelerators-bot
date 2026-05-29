"""Tests for shared scaffold placeholders."""

import pytest
from src.shared.auth import extract_bearer_token, validate_access_token
from src.shared.prompts import get_prompt_templates


@pytest.mark.parametrize(
    ("authorization_header", "expected_token"),
    [
        (None, None),
        ("", None),
        ("Basic abc123", None),
        ("Bearer", None),
        ("Bearer token-123", "token-123"),
        ("bearer token-456", "token-456"),
    ],
)
def test_extract_bearer_token(
    authorization_header: str | None,
    expected_token: str | None,
) -> None:
    """Verify bearer token extraction handles valid and invalid input."""

    assert extract_bearer_token(authorization_header) == expected_token


def test_get_prompt_templates_returns_expected_keys() -> None:
    """Verify the scaffold exposes the shared prompt template names."""

    prompt_templates = get_prompt_templates()

    assert set(prompt_templates) == {"system", "query_rewrite", "answer"}
    assert all(prompt_templates.values())


def test_validate_access_token_raises_placeholder_error() -> None:
    """Verify token validation stays explicit until auth wiring lands."""

    with pytest.raises(NotImplementedError):
        validate_access_token("token-123")
