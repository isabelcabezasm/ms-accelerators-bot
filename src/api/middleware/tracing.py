"""Request tracing middleware for the FastAPI API."""

from __future__ import annotations

import logging
from time import perf_counter
from typing import Any

from fastapi import Request, Response
from opentelemetry import propagate
from opentelemetry.trace import SpanKind, Status, StatusCode
from starlette.middleware.base import (
    BaseHTTPMiddleware,
    RequestResponseEndpoint,
)

from src.api.telemetry import (
    TelemetryManager,
    attach_user_id,
    get_telemetry,
    reset_current_user_id,
    resolve_user_id,
    set_current_user_id,
)

logger = logging.getLogger(__name__)


class TracingMiddleware(BaseHTTPMiddleware):
    """Create one tracing span per incoming FastAPI request."""

    def __init__(
        self,
        app: Any,
        telemetry: TelemetryManager | None = None,
    ) -> None:
        """Initialize the middleware with the shared telemetry manager."""

        super().__init__(app)
        self._telemetry = telemetry or get_telemetry()

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        """Trace request metadata and record request duration metrics."""

        start_time = perf_counter()
        user_id = _resolve_request_user_id(request)
        user_token = set_current_user_id(user_id)
        request.state.user_id = user_id
        span_name = f"{request.method} {request.url.path}"
        trace_context = propagate.extract(dict(request.headers))
        status_code = 500

        with self._telemetry.start_span(
            span_name,
            user_id=user_id,
            attributes={
                "http.method": request.method,
                "http.path": request.url.path,
            },
            kind=SpanKind.SERVER,
            context=trace_context,
        ) as span:
            try:
                response = await call_next(request)
                status_code = response.status_code
                return response
            except Exception as error:
                span.record_exception(error)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception(
                    "Failed while tracing %s %s",
                    request.method,
                    request.url.path,
                )
                raise
            finally:
                duration_ms = (perf_counter() - start_time) * 1000
                span.set_attribute("http.status_code", status_code)
                span.set_attribute("request.duration_ms", duration_ms)
                attach_user_id(span, user_id)
                self._telemetry.record_request_duration(
                    duration_ms,
                    user_id=user_id,
                    attributes={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                    },
                )
                reset_current_user_id(user_token)



def _resolve_request_user_id(request: Request) -> str | None:
    """Resolve the request user identifier from state or JWT claims."""

    explicit_user_id = getattr(request.state, "user_id", None)
    auth_context = getattr(request.state, "auth_context", None)

    return resolve_user_id(
        explicit_user_id=explicit_user_id,
        authorization_header=request.headers.get("Authorization"),
        auth_context=auth_context,
    )
