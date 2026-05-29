"""GitHub README fetching utilities for accelerator ingestion."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.parse import urlparse

import httpx
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


@dataclass(slots=True)
class CachedReadme:
    """Store cached README content keyed by the latest commit SHA."""

    commit_sha: str
    content: str


class SecretReader(Protocol):
    """Define the minimal Key Vault secret client surface the fetcher uses."""

    def get_secret(self, name: str) -> Any:
        """Return the named secret object from the backing store."""


class GitHubFetcherError(RuntimeError):
    """Raise when GitHub README fetching cannot be completed."""


class GitHubRepositoryUrlError(GitHubFetcherError):
    """Raise when an accelerator URL is not a valid GitHub repo URL."""


class GitHubRateLimitError(GitHubFetcherError):
    """Raise when GitHub rate limiting persists beyond retry limits."""


class GitHubBaseUrlError(GitHubFetcherError):
    """Raise when the configured GitHub API base URL is not trusted."""


class GitHubFetcher:
    """Fetch and cache GitHub README documents for accelerator repos."""

    def __init__(
        self,
        key_vault_url: str,
        *,
        secret_name: str = "github-pat",
        credential: DefaultAzureCredential | None = None,
        secret_client: SecretReader | None = None,
        http_client: httpx.AsyncClient | None = None,
        base_url: str = "https://api.github.com",
        allowed_base_url_domains: tuple[str, ...] = (),
        max_retries: int = 3,
        base_backoff_seconds: float = 1.0,
        max_backoff_seconds: float = 30.0,
    ) -> None:
        """Initialize the fetcher with Key Vault and GitHub API clients."""

        validated_base_url = self._validate_base_url(
            base_url,
            allowed_domains=allowed_base_url_domains,
        )
        self._credential = credential or DefaultAzureCredential()
        self._secret_client = secret_client or SecretClient(
            vault_url=key_vault_url,
            credential=self._credential,
        )
        self._http_client = http_client or httpx.AsyncClient(
            base_url=validated_base_url,
            timeout=30.0,
            headers={
                "Accept": "application/vnd.github.raw+json",
                "User-Agent": "ms-accelerators-bot",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        self._owns_http_client = http_client is None
        self._secret_name = secret_name
        self._max_retries = max_retries
        self._base_backoff_seconds = base_backoff_seconds
        self._max_backoff_seconds = max_backoff_seconds
        # Avoid re-fetching README content while the repo HEAD is unchanged.
        self._cache: dict[str, CachedReadme] = {}
        self._token: str | None = None

    async def __aenter__(self) -> GitHubFetcher:
        """Enter the async context manager for the fetcher."""

        return self

    @classmethod
    def _validate_base_url(
        cls,
        base_url: str,
        *,
        allowed_domains: tuple[str, ...],
    ) -> str:
        """Allow only trusted GitHub API hosts for PAT-backed requests."""

        parsed_url = urlparse(base_url)
        hostname = parsed_url.hostname
        if (
            parsed_url.scheme != "https"
            or hostname is None
            or parsed_url.username is not None
            or parsed_url.password is not None
            or bool(parsed_url.query)
            or bool(parsed_url.fragment)
        ):
            raise GitHubBaseUrlError(
                "GitHub API base URL must be an HTTPS URL without "
                "credentials, query parameters, or fragments."
            )

        if cls._is_allowed_base_url_host(
            hostname=hostname,
            allowed_domains=allowed_domains,
        ):
            return base_url

        raise GitHubBaseUrlError(
            "GitHub API base URL must use api.github.com, a "
            "github.com subdomain, or an allow-listed domain."
        )

    @staticmethod
    def _is_allowed_base_url_host(
        hostname: str,
        allowed_domains: tuple[str, ...],
    ) -> bool:
        """Check whether the base URL host is trusted for GitHub API use."""

        normalized_allowed_domains = tuple(
            domain.lower() for domain in allowed_domains if domain
        )
        if hostname == "api.github.com" or hostname.endswith(".github.com"):
            return True

        return any(
            hostname == domain or hostname.endswith(f".{domain}")
            for domain in normalized_allowed_domains
        )

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: Any,
    ) -> None:
        """Close owned HTTP resources when leaving the context manager."""

        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying HTTP client when the fetcher owns it."""

        if self._owns_http_client:
            await self._http_client.aclose()

    @staticmethod
    def parse_repo_url(repository_url: str) -> tuple[str, str]:
        """Parse a GitHub repository URL into owner and repository segments."""

        parsed_url = urlparse(repository_url)
        if parsed_url.netloc not in {"github.com", "www.github.com"}:
            raise GitHubRepositoryUrlError(
                "Accelerator URL must point to github.com/{owner}/{repo}."
            )

        path_parts = [part for part in parsed_url.path.split("/") if part]
        if len(path_parts) < 2:
            raise GitHubRepositoryUrlError(
                "Accelerator URL must include both owner and repository name."
            )

        owner = path_parts[0]
        repo = path_parts[1].removesuffix(".git")
        if not owner or not repo:
            raise GitHubRepositoryUrlError(
                "Accelerator URL must include both owner and repository name."
            )

        return owner, repo

    async def fetch_readme_for_url(self, repository_url: str) -> str:
        """Parse a GitHub repo URL and fetch its README markdown."""

        owner, repo = self.parse_repo_url(repository_url)
        return await self.fetch_readme(owner, repo)

    async def fetch_readme(self, owner: str, repo: str) -> str:
        """Fetch the README markdown for a GitHub repository."""

        default_branch = await self._get_default_branch(owner, repo)
        commit_sha = await self._get_head_commit_sha(
            owner,
            repo,
            default_branch,
        )
        cache_key = self._build_cache_key(owner, repo)

        cached_readme = self._cache.get(cache_key)
        if cached_readme and cached_readme.commit_sha == commit_sha:
            return cached_readme.content

        readme_response = await self._request(
            f"/repos/{owner}/{repo}/readme",
        )
        cleaned_markdown = self.clean_markdown(readme_response.text)
        self._cache[cache_key] = CachedReadme(
            commit_sha=commit_sha,
            content=cleaned_markdown,
        )
        return cleaned_markdown

    @staticmethod
    def clean_markdown(markdown: str) -> str:
        """Normalize raw README markdown before downstream ingestion."""

        normalized = markdown.lstrip("\ufeff")
        normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
        stripped_lines = [line.rstrip() for line in normalized.split("\n")]
        return "\n".join(stripped_lines).strip()

    async def _get_default_branch(self, owner: str, repo: str) -> str:
        """Fetch the default branch name for a repository."""

        response = await self._request(f"/repos/{owner}/{repo}")
        payload = response.json()
        default_branch = payload.get("default_branch")
        if not isinstance(default_branch, str) or not default_branch:
            raise GitHubFetcherError(
                "GitHub repository "
                f"{owner}/{repo} did not return a default branch."
            )

        return default_branch

    async def _get_head_commit_sha(
        self,
        owner: str,
        repo: str,
        branch_name: str,
    ) -> str:
        """Fetch the latest commit SHA for the branch used by the README."""

        response = await self._request(
            f"/repos/{owner}/{repo}/branches/{branch_name}",
        )
        payload = response.json()
        commit = payload.get("commit")
        if not isinstance(commit, dict):
            raise GitHubFetcherError(
                f"GitHub branch metadata for {owner}/{repo} is incomplete."
            )

        commit_sha = commit.get("sha")
        if not isinstance(commit_sha, str) or not commit_sha:
            raise GitHubFetcherError(
                f"GitHub branch metadata for {owner}/{repo} is missing a SHA."
            )

        return commit_sha

    async def _request(self, path: str) -> httpx.Response:
        """Issue a GitHub API request with auth and rate-limit retries."""

        headers = await self._get_auth_headers()

        for attempt in range(self._max_retries + 1):
            response = await self._http_client.get(path, headers=headers)
            if self._is_rate_limited(response):
                if attempt >= self._max_retries:
                    raise GitHubRateLimitError(
                        f"GitHub API rate limit exceeded for {path}."
                    )

                await asyncio.sleep(
                    self._get_backoff_delay(response, attempt),
                )
                continue

            await self._respect_rate_limit_headers(response)

            if response.is_error:
                raise GitHubFetcherError(
                    f"GitHub API request failed for {path}: "
                    f"{response.status_code} {response.text}"
                )

            return response

        raise GitHubFetcherError(
            f"GitHub API request unexpectedly ended for {path}."
        )

    async def _get_auth_headers(self) -> dict[str, str]:
        """Build authenticated GitHub API headers using a Key Vault PAT."""

        token = await self._get_token()
        return {"Authorization": f"Bearer {token}"}

    async def _get_token(self) -> str:
        """Load and cache the GitHub PAT from Azure Key Vault."""

        if self._token is not None:
            return self._token

        secret = await asyncio.to_thread(
            self._secret_client.get_secret,
            self._secret_name,
        )
        token = secret.value
        if not token:
            raise GitHubFetcherError(
                f"GitHub PAT secret '{self._secret_name}' is empty."
            )

        self._token = token
        return token

    async def _respect_rate_limit_headers(
        self,
        response: httpx.Response,
    ) -> None:
        """Pause until reset when the current response exhausts the budget."""

        if response.headers.get("X-RateLimit-Remaining") != "0":
            return

        reset_delay = self._get_reset_delay(response)
        if reset_delay > 0:
            await asyncio.sleep(reset_delay)

    def _get_backoff_delay(
        self,
        response: httpx.Response,
        attempt: int,
    ) -> float:
        """Calculate the retry delay for a rate-limited GitHub response."""

        retry_after = response.headers.get("Retry-After")
        if retry_after is not None:
            try:
                return max(float(retry_after), 0.0)
            except ValueError:
                pass

        reset_delay = self._get_reset_delay(response)
        if reset_delay > 0:
            return reset_delay

        exponential_delay = self._base_backoff_seconds * (2**attempt)
        return min(exponential_delay, self._max_backoff_seconds)

    def _get_reset_delay(self, response: httpx.Response) -> float:
        """Translate the rate-limit reset header into seconds to wait."""

        reset_value = response.headers.get("X-RateLimit-Reset")
        if reset_value is None:
            return 0.0

        try:
            reset_timestamp = float(reset_value)
        except ValueError:
            return 0.0

        now_timestamp = datetime.now(tz=UTC).timestamp()
        return max(reset_timestamp - now_timestamp, 0.0)

    @staticmethod
    def _is_rate_limited(response: httpx.Response) -> bool:
        """Determine whether the response signals a GitHub rate limit."""

        if response.status_code == 429:
            return True

        return (
            response.status_code == 403
            and response.headers.get("X-RateLimit-Remaining") == "0"
        )

    @staticmethod
    def _build_cache_key(owner: str, repo: str) -> str:
        """Create a stable cache key for a repository."""

        return f"{owner.lower()}/{repo.lower()}"
