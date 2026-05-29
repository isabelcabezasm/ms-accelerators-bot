"""Telemetry helpers for FastAPI observability."""

from __future__ import annotations

import base64
import hashlib
import json
import logging
from collections.abc import Iterator, Mapping
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from threading import Lock
from typing import Any

from azure.monitor.opentelemetry.exporter import (
    AzureMonitorMetricExporter,
    AzureMonitorTraceExporter,
)
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import Span, SpanKind, Tracer

from src.shared.auth import AuthContext, extract_bearer_token

logger = logging.getLogger(__name__)

_USER_ID_CONTEXT: ContextVar[str | None] = ContextVar(
    "telemetry_user_id",
    default=None,
)
type TelemetryAttributeValue = str | int | float | bool

_USER_CLAIM_KEYS: tuple[str, ...] = ("sub",)
_SENSITIVE_SPAN_ATTRIBUTE_KEYS = frozenset(
    {
        "email",
        "enduser.name",
        "family_name",
        "given_name",
        "name",
        "preferred_username",
        "upn",
        "user.email",
        "user.name",
    }
)
_MAX_ATTRIBUTE_LENGTH = 512
_TELEMETRY_LOCK = Lock()
_TELEMETRY_MANAGER: TelemetryManager | None = None


@dataclass(slots=True)
class TelemetryManager:
    """Bundle tracing and metrics primitives for the API."""

    tracer_provider: TracerProvider
    meter_provider: MeterProvider
    tracer: Tracer
    meter: Meter
    request_duration: Histogram
    token_usage: Counter
    search_latency: Histogram

    def instrument_fastapi(self, app: FastAPI) -> None:
        """Attach FastAPI instrumentation when the app opts in."""

        if getattr(app.state, "telemetry_instrumented", False):
            return

        FastAPIInstrumentor.instrument_app(
            app,
            tracer_provider=self.tracer_provider,
            meter_provider=self.meter_provider,
            excluded_urls="/healthz",
        )
        app.state.telemetry_instrumented = True

    @contextmanager
    def start_span(
        self,
        name: str,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
        kind: SpanKind = SpanKind.INTERNAL,
        context: Any | None = None,
    ) -> Iterator[Span]:
        """Start a span enriched with the resolved user identifier."""

        span_attributes = sanitize_span_attributes(attributes)
        resolved_user_id = user_id or get_current_user_id()
        span_attributes.update(build_user_attributes(resolved_user_id))

        with self.tracer.start_as_current_span(
            name,
            context=context,
            kind=kind,
            attributes=span_attributes,
        ) as span:
            yield span

    def start_search_retrieval_span(
        self,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager[Span]:
        """Create the retrieval span used around search operations."""

        return self.start_span(
            "search_retrieval",
            user_id=user_id,
            attributes=attributes,
        )

    def start_llm_generation_span(
        self,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager[Span]:
        """Create the generation span used around LLM calls."""

        return self.start_span(
            "llm_generation",
            user_id=user_id,
            attributes=attributes,
        )

    def start_embedding_span(
        self,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> AbstractContextManager[Span]:
        """Create the embedding span used around vector generation."""

        return self.start_span(
            "embedding",
            user_id=user_id,
            attributes=attributes,
        )

    def record_request_duration(
        self,
        duration_ms: float,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record request latency with the resolved user dimensions."""

        self.request_duration.record(
            duration_ms,
            attributes=_metric_attributes(attributes, user_id),
        )

    def record_token_usage(
        self,
        tokens: int,
        *,
        operation: str,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record token usage for generation or embedding workloads."""

        metric_attributes = dict(attributes or {})
        metric_attributes["operation"] = operation
        self.token_usage.add(
            tokens,
            attributes=_metric_attributes(metric_attributes, user_id),
        )

    def record_search_latency(
        self,
        duration_ms: float,
        *,
        user_id: str | None = None,
        attributes: Mapping[str, Any] | None = None,
    ) -> None:
        """Record Azure AI Search latency with request dimensions."""

        self.search_latency.record(
            duration_ms,
            attributes=_metric_attributes(attributes, user_id),
        )


@contextmanager
def use_user_id(user_id: str | None) -> Iterator[None]:
    """Temporarily bind a user identifier to the current context."""

    token = set_current_user_id(user_id)
    try:
        yield
    finally:
        reset_current_user_id(token)


def set_current_user_id(user_id: str | None) -> Token[str | None]:
    """Store a user identifier in the active context."""

    return _USER_ID_CONTEXT.set(user_id)



def reset_current_user_id(token: Token[str | None]) -> None:
    """Restore the prior user identifier after request processing."""

    _USER_ID_CONTEXT.reset(token)



def get_current_user_id() -> str | None:
    """Return the current request user identifier, if one exists."""

    return _USER_ID_CONTEXT.get()



def hash_user_id(user_id: str | None) -> str | None:
    """Hash a user identifier before emitting it in telemetry."""

    if user_id is None:
        return None

    normalized_user_id = user_id.strip()
    if not normalized_user_id:
        return None

    return hashlib.sha256(normalized_user_id.encode("utf-8")).hexdigest()



def sanitize_span_attributes(
    attributes: Mapping[str, Any] | None,
) -> dict[str, TelemetryAttributeValue]:
    """Filter span attributes to safe scalar values without PII."""

    span_attributes: dict[str, TelemetryAttributeValue] = {}
    for key, value in dict(attributes or {}).items():
        if not isinstance(key, str) or _is_sensitive_span_attribute(key):
            continue

        sanitized_value = _sanitize_telemetry_value(value)
        if sanitized_value is not None:
            span_attributes[key] = sanitized_value

    return span_attributes



def build_user_attributes(user_id: str | None) -> dict[str, str]:
    """Build span attributes for the current user dimensions."""

    hashed_user_id = hash_user_id(user_id)
    if hashed_user_id is None:
        return {}

    return {
        "userId": hashed_user_id,
        "enduser.id": hashed_user_id,
    }



def attach_user_id(span: Span, user_id: str | None = None) -> str | None:
    """Attach the hashed user identifier to an existing span."""

    resolved_user_id = user_id or get_current_user_id()
    hashed_user_id = hash_user_id(resolved_user_id)
    for key, value in build_user_attributes(resolved_user_id).items():
        span.set_attribute(key, value)
    return hashed_user_id



def extract_user_id_from_auth_context(
    auth_context: AuthContext | None,
) -> str | None:
    """Return the user identifier from an auth context when available."""

    if auth_context is None:
        return None

    return auth_context.user_id



def decode_jwt_claims(token: str) -> Mapping[str, Any] | None:
    """Decode JWT payload claims without validating the signature."""

    parts = token.split(".")
    if len(parts) != 3:
        return None

    payload = parts[1]
    padding = "=" * (-len(payload) % 4)

    try:
        decoded_payload = base64.urlsafe_b64decode(f"{payload}{padding}")
        claims = json.loads(decoded_payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        logger.debug("Unable to decode JWT claims for telemetry.")
        return None

    if isinstance(claims, dict):
        return claims

    return None



def extract_user_id_from_claims(
    claims: Mapping[str, Any] | None,
) -> str | None:
    """Resolve the telemetry subject identifier from JWT claims."""

    if claims is None:
        return None

    for claim_name in _USER_CLAIM_KEYS:
        claim_value = claims.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value.strip()

    return None



def resolve_user_id(
    *,
    explicit_user_id: str | None = None,
    authorization_header: str | None = None,
    auth_context: AuthContext | None = None,
) -> str | None:
    """Resolve the best user identifier available for telemetry data."""

    if explicit_user_id and explicit_user_id.strip():
        return explicit_user_id.strip()

    context_user_id = extract_user_id_from_auth_context(auth_context)
    if context_user_id and context_user_id.strip():
        return context_user_id.strip()

    bearer_token = extract_bearer_token(authorization_header)
    if not bearer_token:
        return None

    return extract_user_id_from_claims(decode_jwt_claims(bearer_token))



def _is_sensitive_span_attribute(key: str) -> bool:
    """Return whether a span attribute key can contain direct PII."""

    normalized_key = key.strip().casefold()
    if normalized_key in _SENSITIVE_SPAN_ATTRIBUTE_KEYS:
        return True

    return normalized_key.endswith(".email")



def _sanitize_telemetry_value(value: Any) -> TelemetryAttributeValue | None:
    """Convert telemetry values to safe scalar attributes."""

    if isinstance(value, bool | int | float):
        return value

    if not isinstance(value, str):
        return None

    normalized_value = "".join(
        character if character.isprintable() else " "
        for character in value
    )
    normalized_value = " ".join(normalized_value.split())
    return normalized_value[:_MAX_ATTRIBUTE_LENGTH]



def configure_telemetry(
    app_name: str,
    connection_string: str | None = None,
    *,
    reset: bool = False,
    enable_metric_exporter: bool = True,
) -> TelemetryManager:
    """Create the shared telemetry manager used by the API."""

    global _TELEMETRY_MANAGER

    with _TELEMETRY_LOCK:
        if _TELEMETRY_MANAGER is not None and not reset:
            return _TELEMETRY_MANAGER

        resource = Resource.create(
            {
                "service.name": app_name,
                "service.namespace": "src.api",
            }
        )
        tracer_provider = TracerProvider(resource=resource)

        if connection_string:
            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    AzureMonitorTraceExporter(
                        connection_string=connection_string,
                        disable_offline_storage=True,
                    )
                )
            )

        metric_readers = []
        if connection_string and enable_metric_exporter:
            metric_readers.append(
                PeriodicExportingMetricReader(
                    AzureMonitorMetricExporter(
                        connection_string=connection_string,
                        disable_offline_storage=True,
                    )
                )
            )

        meter_provider = MeterProvider(
            resource=resource,
            metric_readers=metric_readers,
        )
        meter = meter_provider.get_meter("src.api.telemetry")

        _TELEMETRY_MANAGER = TelemetryManager(
            tracer_provider=tracer_provider,
            meter_provider=meter_provider,
            tracer=tracer_provider.get_tracer("src.api.telemetry"),
            meter=meter,
            request_duration=meter.create_histogram(
                name="request_duration",
                unit="ms",
                description="HTTP request duration in milliseconds.",
            ),
            token_usage=meter.create_counter(
                name="token_usage",
                unit="{token}",
                description="Total tokens consumed by AI operations.",
            ),
            search_latency=meter.create_histogram(
                name="search_latency",
                unit="ms",
                description="Azure AI Search latency in milliseconds.",
            ),
        )

        return _TELEMETRY_MANAGER



def get_telemetry() -> TelemetryManager:
    """Return the configured telemetry manager for the API."""

    if _TELEMETRY_MANAGER is None:
        return configure_telemetry("Microsoft Accelerators Finder API")

    return _TELEMETRY_MANAGER



def reset_telemetry() -> None:
    """Reset the cached telemetry manager for isolated tests."""

    global _TELEMETRY_MANAGER
    _TELEMETRY_MANAGER = None



def _metric_attributes(
    attributes: Mapping[str, Any] | None,
    user_id: str | None,
) -> dict[str, TelemetryAttributeValue]:
    """Normalize metric dimensions before recording measurements."""

    metric_attributes = sanitize_span_attributes(attributes)

    hashed_user_id = hash_user_id(user_id or get_current_user_id())
    if hashed_user_id is not None:
        metric_attributes["userId"] = hashed_user_id

    return metric_attributes
