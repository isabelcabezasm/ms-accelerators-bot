"""Tests for OpenTelemetry wiring and request tracing."""

from __future__ import annotations

import base64
import hashlib
import json
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from opentelemetry.sdk.trace.export import (
    SimpleSpanProcessor,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import (
    NonRecordingSpan,
    SpanContext,
    TraceFlags,
    TraceState,
    set_span_in_context,
)
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from src.api.middleware.tracing import TracingMiddleware
from src.api.telemetry import (
    configure_telemetry,
    reset_telemetry,
    use_user_id,
)


class FakeAzureMonitorTraceExporter:
    """Capture Azure Monitor exporter initialization in tests."""

    instances: list[FakeAzureMonitorTraceExporter] = []

    def __init__(self, **kwargs: Any) -> None:
        """Store exporter keyword arguments for later assertions."""

        self.kwargs = kwargs
        self.exported: list[Any] = []
        type(self).instances.append(self)

    def export(self, spans: Any) -> SpanExportResult:
        """Collect spans without sending them to Azure Monitor."""

        self.exported.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        """Satisfy the exporter interface used by BatchSpanProcessor."""

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        """Satisfy the exporter interface used by BatchSpanProcessor."""

        return True


@pytest.fixture(autouse=True)
def reset_test_telemetry() -> Iterator[None]:
    """Reset the cached telemetry manager around every test case."""

    reset_telemetry()
    FakeAzureMonitorTraceExporter.instances.clear()
    yield
    reset_telemetry()
    FakeAzureMonitorTraceExporter.instances.clear()



def test_configure_telemetry_mocks_azure_monitor_exporter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create the Azure Monitor exporter without touching external services."""

    from src.api import telemetry

    monkeypatch.setattr(
        telemetry,
        "AzureMonitorTraceExporter",
        FakeAzureMonitorTraceExporter,
    )

    configure_telemetry(
        "test-api",
        connection_string="InstrumentationKey=test-key",
        reset=True,
        enable_metric_exporter=False,
    )

    assert len(FakeAzureMonitorTraceExporter.instances) == 1
    exporter = FakeAzureMonitorTraceExporter.instances[0]
    assert exporter.kwargs["connection_string"] == (
        "InstrumentationKey=test-key"
    )
    assert exporter.kwargs["disable_offline_storage"] is True



def test_custom_spans_include_hashed_user_id() -> None:
    """Attach only a hashed user identifier to custom telemetry spans."""

    telemetry = configure_telemetry("test-api", reset=True)
    span_exporter = InMemorySpanExporter()
    telemetry.tracer_provider.add_span_processor(
        SimpleSpanProcessor(span_exporter)
    )

    with use_user_id("user-123"):
        with telemetry.start_search_retrieval_span():
            pass
        with telemetry.start_llm_generation_span():
            pass
        with telemetry.start_embedding_span():
            pass

    spans = span_exporter.get_finished_spans()
    assert [span.name for span in spans] == [
        "search_retrieval",
        "llm_generation",
        "embedding",
    ]
    expected_user_id = _hash_user_id("user-123")
    assert all(
        (span.attributes or {}).get("userId") == expected_user_id
        for span in spans
    )
    assert all(
        (span.attributes or {}).get("enduser.id") == expected_user_id
        for span in spans
    )



def test_tracing_middleware_captures_request_metadata() -> None:
    """Create a request span with sanitized attributes and correlation."""

    telemetry = configure_telemetry("test-api", reset=True)
    span_exporter = InMemorySpanExporter()
    telemetry.tracer_provider.add_span_processor(
        SimpleSpanProcessor(span_exporter)
    )

    app = FastAPI()
    app.add_middleware(TracingMiddleware, telemetry=telemetry)

    @app.get("/telemetry")
    async def telemetry_route(request: Request) -> JSONResponse:
        """Echo the resolved user identifier for middleware assertions."""

        return JSONResponse({"user_id": request.state.user_id})

    parent_context = SpanContext(
        trace_id=0x1234567890ABCDEF1234567890ABCDEF,
        span_id=0x1234567890ABCDEF,
        is_remote=True,
        trace_flags=TraceFlags(0x01),
        trace_state=TraceState(),
    )
    jwt_claims = {
        "sub": "request-user",
        "email": "user@example.com",
        "name": "Example User",
    }
    carrier: dict[str, str] = {
        "Authorization": f"Bearer {_build_jwt(jwt_claims)}",
    }
    TraceContextTextMapPropagator().inject(
        carrier,
        context=set_span_in_context(NonRecordingSpan(parent_context)),
    )

    client = TestClient(app)
    response = client.get("/telemetry", headers=carrier)

    assert response.status_code == 200
    assert response.json() == {"user_id": "request-user"}

    request_span = _find_span(
        span_exporter.get_finished_spans(),
        "GET /telemetry",
    )
    assert request_span is not None
    assert request_span.parent is not None
    assert request_span.parent.span_id == parent_context.span_id
    attributes = request_span.attributes or {}
    assert attributes["http.method"] == "GET"
    assert attributes["http.path"] == "/telemetry"
    assert attributes["http.status_code"] == 200
    assert attributes["userId"] == _hash_user_id("request-user")
    assert attributes["enduser.id"] == _hash_user_id("request-user")
    assert attributes["request.duration_ms"] >= 0
    assert "user@example.com" not in repr(attributes)
    assert "Example User" not in repr(attributes)



def test_start_span_sanitizes_user_attributes() -> None:
    """Drop PII fields and normalize user text before span creation."""

    telemetry = configure_telemetry("test-api", reset=True)
    span_exporter = InMemorySpanExporter()
    telemetry.tracer_provider.add_span_processor(
        SimpleSpanProcessor(span_exporter)
    )

    with telemetry.start_llm_generation_span(
        user_id="subject-123",
        attributes={
            "prompt": "hello\n<script>\tworld",
            "email": "user@example.com",
            "name": "Example User",
            "attempt": 1,
            "metadata": {"unsafe": True},
        },
    ):
        pass

    span = _find_span(span_exporter.get_finished_spans(), "llm_generation")
    assert span is not None
    attributes = span.attributes or {}
    assert attributes["prompt"] == "hello <script> world"
    assert attributes["attempt"] == 1
    assert attributes["userId"] == _hash_user_id("subject-123")
    assert "email" not in attributes
    assert "name" not in attributes
    assert "metadata" not in attributes



def _build_jwt(claims: dict[str, str]) -> str:
    """Build a compact unsigned JWT for middleware telemetry tests."""

    header = _encode_segment({"alg": "none", "typ": "JWT"})
    payload = _encode_segment(claims)
    return f"{header}.{payload}.signature"



def _encode_segment(payload: dict[str, str]) -> str:
    """Base64-url encode one JWT segment without padding characters."""

    encoded = json.dumps(payload).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("utf-8").rstrip("=")



def _find_span(spans: tuple[Any, ...], name: str) -> Any:
    """Return the first span whose name matches the requested value."""

    for span in spans:
        if span.name == name:
            return span

    return None



def _hash_user_id(user_id: str) -> str:
    """Return the SHA-256 digest used for telemetry user identifiers."""

    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()
