"""Simple in-memory rate limiting utilities for FastAPI."""

from __future__ import annotations

import time
from collections import defaultdict, deque
from functools import lru_cache
from threading import Lock
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class RateLimitSettings(BaseSettings):
    """Load rate-limit configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="",
        extra="ignore",
        populate_by_name=True,
    )

    rate_limit_requests: int = Field(
        default=30,
        alias="RATE_LIMIT_REQUESTS",
        ge=1,
    )
    rate_limit_window: int = Field(
        default=60,
        alias="RATE_LIMIT_WINDOW",
        ge=1,
    )
    trusted_proxy_count: int = Field(
        default=0,
        alias="TRUSTED_PROXY_COUNT",
        ge=0,
    )


class InMemoryRateLimiter:
    """Enforce a sliding-window rate limit per caller identifier."""

    def __init__(self, *, max_requests: int, window_seconds: int) -> None:
        """Store the limit settings and allocate request buckets."""

        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._requests: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return whether the caller is allowed and the retry delay."""

        now = time.monotonic()
        with self._lock:
            bucket = self._requests[key]
            self._prune(bucket, now)
            if len(bucket) >= self._max_requests:
                retry_after = max(
                    1,
                    int(self._window_seconds - (now - bucket[0])) + 1,
                )
                return False, retry_after
            bucket.append(now)
            return True, 0

    def _prune(self, bucket: deque[float], now: float) -> None:
        """Drop timestamps that are outside the active rate window."""

        cutoff = now - self._window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()


@lru_cache
def get_rate_limit_settings() -> RateLimitSettings:
    """Load and cache rate-limit settings for request handling."""

    return RateLimitSettings()


@lru_cache
def get_rate_limiter() -> InMemoryRateLimiter:
    """Create and cache the configured in-memory rate limiter."""

    settings = get_rate_limit_settings()
    return InMemoryRateLimiter(
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window,
    )


def get_direct_client_host(request: Request) -> str | None:
    """Return the peer address reported by the ASGI server."""

    client = request.client
    if client is None or not client.host:
        return None
    return client.host


def get_forwarded_client_host(
    request: Request,
    *,
    trusted_proxy_count: int,
) -> str | None:
    """Return the last untrusted X-Forwarded-For hop when trusted."""

    if trusted_proxy_count <= 0:
        return None

    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if not forwarded_for:
        return None

    forwarded_hosts = [
        host.strip() for host in forwarded_for.split(",") if host.strip()
    ]
    if len(forwarded_hosts) < trusted_proxy_count:
        return None

    return forwarded_hosts[-trusted_proxy_count]


def get_request_identifier(
    request: Request,
    *,
    settings: RateLimitSettings | None = None,
) -> str:
    """Resolve the caller identifier from direct or trusted proxy data."""

    resolved_settings = settings or get_rate_limit_settings()
    direct_host = get_direct_client_host(request)
    forwarded_host = get_forwarded_client_host(
        request,
        trusted_proxy_count=resolved_settings.trusted_proxy_count,
    )
    if forwarded_host:
        return forwarded_host
    if direct_host:
        return direct_host
    return "anonymous"


def enforce_rate_limit(
    request: Request,
    rate_limiter: Annotated[
        InMemoryRateLimiter,
        Depends(get_rate_limiter),
    ],
) -> None:
    """Reject callers that exceed the configured anonymous request budget."""

    key = get_request_identifier(request)
    allowed, retry_after = rate_limiter.check(key)
    if allowed:
        return
    raise HTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        detail="Rate limit exceeded. Try again later.",
        headers={"Retry-After": str(retry_after)},
    )
