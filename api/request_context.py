"""Утилиты для единого контекста HTTP-запроса API."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from flask import g, request

_REQUEST_ID_HEADER = "X-Request-ID"


@dataclass(frozen=True)
class RequestContext:
    """Структура контекста входящего HTTP-запроса."""

    request_id: str
    trace_id: str
    client_ip: str


def ensure_request_context() -> RequestContext:
    """Инициализирует и возвращает единый request/trace контекст."""
    request_id = getattr(g, "request_id", None)
    if not request_id:
        header_value = request.headers.get(_REQUEST_ID_HEADER, "").strip()
        request_id = header_value or uuid.uuid4().hex
        g.request_id = request_id

    trace_id = getattr(g, "trace_id", None)
    if not trace_id:
        trace_id = str(request_id)
        g.trace_id = trace_id

    client_ip = getattr(g, "client_ip", None)
    if not client_ip:
        client_ip = request.remote_addr or "unknown"
        g.client_ip = client_ip

    return RequestContext(
        request_id=str(request_id),
        trace_id=str(trace_id),
        client_ip=str(client_ip),
    )
