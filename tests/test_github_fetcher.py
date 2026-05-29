"""Tests for the GitHub README fetcher."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import pytest
import src.ingestion.github_fetcher as github_fetcher_module
from src.ingestion.github_fetcher import (
    GitHubFetcher,
    GitHubRateLimitError,
    GitHubRepositoryUrlError,
)


class FakeSecret:
    """Represent a Key Vault secret value for tests."""

    def __init__(self, value: str) -> None:
        """Store the test secret value."""

        self.value = value


class FakeSecretClient:
    """Provide a predictable Key Vault client for unit tests."""

    def __init__(self, token: str = "test-token") -> None:
        """Initialize the fake client with a secret token."""

        self._token = token
        self.calls = 0

    def get_secret(self, name: str) -> FakeSecret:
        """Return the configured token and track how often it is loaded."""

        self.calls += 1
        assert name == "github-pat"
        return FakeSecret(self._token)


def build_response(
    status_code: int,
    request: httpx.Request,
    *,
    json_body: dict[str, Any] | None = None,
    text: str = "",
    headers: dict[str, str] | None = None,
) -> httpx.Response:
    """Build a mock HTTP response for the GitHub API transport."""

    return httpx.Response(
        status_code=status_code,
        json=json_body,
        text=None if json_body is not None else text,
        headers=headers,
        request=request,
    )


@pytest.mark.asyncio
async def test_fetch_readme_uses_commit_cache_and_cleans_markdown() -> None:
    """Fetch README once and reuse the cached content for the same SHA."""

    call_counts: dict[str, int] = {
        "repo": 0,
        "branch": 0,
        "readme": 0,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        assert request.headers["Authorization"] == "Bearer test-token"
        if path == "/repos/octo/demo":
            call_counts["repo"] += 1
            return build_response(
                200,
                request,
                json_body={"default_branch": "main"},
                headers={"X-RateLimit-Remaining": "10"},
            )
        if path == "/repos/octo/demo/branches/main":
            call_counts["branch"] += 1
            return build_response(
                200,
                request,
                json_body={"commit": {"sha": "abc123"}},
                headers={"X-RateLimit-Remaining": "10"},
            )
        if path == "/repos/octo/demo/readme":
            call_counts["readme"] += 1
            return build_response(
                200,
                request,
                text="\ufeff# Demo\r\n\r\nLine with space   \r\n",
                headers={"X-RateLimit-Remaining": "10"},
            )
        raise AssertionError(f"Unexpected request path: {path}")

    client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    secret_client = FakeSecretClient()
    fetcher = GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        secret_client=secret_client,
        http_client=client,
    )

    first_readme = await fetcher.fetch_readme("octo", "demo")
    second_readme = await fetcher.fetch_readme("octo", "demo")

    assert first_readme == "# Demo\n\nLine with space"
    assert second_readme == first_readme
    assert call_counts == {"repo": 2, "branch": 2, "readme": 1}
    assert secret_client.calls == 1

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_readme_for_url_parses_owner_and_repo() -> None:
    """Parse a GitHub URL and route the fetch through the owner/repo API."""

    seen_paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_paths.append(request.url.path)
        if request.url.path == "/repos/octo/demo":
            return build_response(
                200,
                request,
                json_body={"default_branch": "main"},
                headers={"X-RateLimit-Remaining": "10"},
            )
        if request.url.path == "/repos/octo/demo/branches/main":
            return build_response(
                200,
                request,
                json_body={"commit": {"sha": "sha-1"}},
                headers={"X-RateLimit-Remaining": "10"},
            )
        if request.url.path == "/repos/octo/demo/readme":
            return build_response(
                200,
                request,
                text="# Parsed",
                headers={"X-RateLimit-Remaining": "10"},
            )
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    fetcher = GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        secret_client=FakeSecretClient(),
        http_client=client,
    )

    readme = await fetcher.fetch_readme_for_url("https://github.com/octo/demo")

    assert readme == "# Parsed"
    assert seen_paths == [
        "/repos/octo/demo",
        "/repos/octo/demo/branches/main",
        "/repos/octo/demo/readme",
    ]

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_readme_retries_after_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Retry the API call with backoff when GitHub returns 429."""

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(github_fetcher_module.asyncio, "sleep", fake_sleep)

    responses_by_path: dict[
        str,
        list[object],
    ] = {
        "/repos/octo/demo": [
            lambda request: build_response(
                429,
                request,
                headers={"Retry-After": "2"},
            ),
            lambda request: build_response(
                200,
                request,
                json_body={"default_branch": "main"},
                headers={"X-RateLimit-Remaining": "10"},
            ),
        ],
        "/repos/octo/demo/branches/main": [
            lambda request: build_response(
                200,
                request,
                json_body={"commit": {"sha": "sha-2"}},
                headers={"X-RateLimit-Remaining": "10"},
            ),
        ],
        "/repos/octo/demo/readme": [
            lambda request: build_response(
                200,
                request,
                text="# Retried",
                headers={"X-RateLimit-Remaining": "10"},
            ),
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        response_factory = responses_by_path[request.url.path].pop(0)
        assert callable(response_factory)
        return response_factory(request)

    client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    fetcher = GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        secret_client=FakeSecretClient(),
        http_client=client,
    )

    readme = await fetcher.fetch_readme("octo", "demo")

    assert readme == "# Retried"
    assert sleep_calls == [2.0]

    await client.aclose()


@pytest.mark.asyncio
async def test_fetch_readme_waits_for_rate_limit_reset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pause when GitHub reports that the current budget is exhausted."""

    sleep_calls: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(github_fetcher_module.asyncio, "sleep", fake_sleep)

    reset_at = datetime.now(tz=UTC) + timedelta(seconds=5)
    reset_header = str(int(reset_at.timestamp()))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/repos/octo/demo":
            return build_response(
                200,
                request,
                json_body={"default_branch": "main"},
                headers={
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": reset_header,
                },
            )
        if request.url.path == "/repos/octo/demo/branches/main":
            return build_response(
                200,
                request,
                json_body={"commit": {"sha": "sha-3"}},
                headers={"X-RateLimit-Remaining": "10"},
            )
        if request.url.path == "/repos/octo/demo/readme":
            return build_response(
                200,
                request,
                text="# Limited",
                headers={"X-RateLimit-Remaining": "10"},
            )
        raise AssertionError(f"Unexpected request path: {request.url.path}")

    client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    fetcher = GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        secret_client=FakeSecretClient(),
        http_client=client,
    )

    readme = await fetcher.fetch_readme("octo", "demo")

    assert readme == "# Limited"
    assert len(sleep_calls) == 1
    assert 0.0 <= sleep_calls[0] <= 5.0

    await client.aclose()


def test_parse_repo_url_rejects_invalid_urls() -> None:
    """Reject non-GitHub URLs that cannot be mapped to a repository."""

    with pytest.raises(GitHubRepositoryUrlError):
        GitHubFetcher.parse_repo_url("https://example.com/octo/demo")


def test_fetcher_builds_secret_client_from_default_credential(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construct the Key Vault secret client from the default credential."""

    seen: dict[str, Any] = {}

    class FakeCredential:
        """Stand in for DefaultAzureCredential during the test."""

    class CapturingSecretClient:
        """Capture constructor arguments for the SecretClient."""

        def __init__(self, *, vault_url: str, credential: Any) -> None:
            seen["vault_url"] = vault_url
            seen["credential"] = credential

        def get_secret(self, name: str) -> FakeSecret:
            return FakeSecret("test-token")

    monkeypatch.setattr(
        github_fetcher_module,
        "DefaultAzureCredential",
        FakeCredential,
    )
    monkeypatch.setattr(
        github_fetcher_module,
        "SecretClient",
        CapturingSecretClient,
    )

    GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        http_client=httpx.AsyncClient(),
    )

    assert seen["vault_url"] == "https://vault.example.vault.azure.net/"
    assert isinstance(seen["credential"], FakeCredential)


@pytest.mark.asyncio
async def test_fetch_readme_raises_after_exhausting_rate_limit_retries(
) -> None:
    """Raise a dedicated error when rate limiting never clears."""

    def handler(request: httpx.Request) -> httpx.Response:
        return build_response(
            429,
            request,
            headers={"Retry-After": "0"},
        )

    client = httpx.AsyncClient(
        base_url="https://api.github.com",
        transport=httpx.MockTransport(handler),
    )
    fetcher = GitHubFetcher(
        key_vault_url="https://vault.example.vault.azure.net/",
        secret_client=FakeSecretClient(),
        http_client=client,
        max_retries=1,
    )

    with pytest.raises(GitHubRateLimitError):
        await fetcher.fetch_readme("octo", "demo")

    await client.aclose()
