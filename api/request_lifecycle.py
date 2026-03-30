"""Регистрация request lifecycle middleware для API."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from flask import Flask, g, jsonify, request

from api.request_context import ensure_request_context
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class _Observability(Protocol):
    """Минимальный контракт observability для request middleware."""

    def request_started(self) -> None:
        """Фиксирует старт обработки запроса."""

    def request_finished(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        latency_seconds: float,
    ) -> None:
        """Фиксирует завершение обработки запроса."""


def register_request_lifecycle(
    app: Flask,
    *,
    request_id_header: str,
    observability: _Observability,
    health_payload_factory: Callable[[], dict[str, Any]],
    access_log_level_resolver: Callable[[str, int], int],
) -> None:
    """Регистрирует before/after-request middleware для API сервера."""

    @app.before_request
    def assign_request_id() -> Any | None:
        request_context = ensure_request_context()
        g.request_id = request_context.request_id
        g.trace_id = request_context.trace_id
        g.client_ip = request_context.client_ip
        g.request_started_at = time.monotonic()
        observability.request_started()

        if request.path == "/health":
            return jsonify(health_payload_factory())
        return None

    @app.after_request
    def add_request_id_header(response: Any) -> Any:
        request_context = ensure_request_context()
        response.headers[request_id_header] = request_context.request_id

        started_at = getattr(g, "request_started_at", None)
        latency_ms = 0.0
        if isinstance(started_at, float):
            latency_seconds = max(0.0, time.monotonic() - started_at)
            latency_ms = latency_seconds * 1000.0
            observability.request_finished(
                method=request.method,
                path=request.path,
                status_code=response.status_code,
                latency_seconds=latency_seconds,
            )

        logger.log(
            access_log_level_resolver(
                request.path,
                response.status_code,
            ),
            "API %s %s -> %s (%.2f ms) request_id=%s ip=%s",
            request.method,
            request.path,
            response.status_code,
            latency_ms,
            request_context.request_id,
            request_context.client_ip,
        )
        return response
