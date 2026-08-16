"""Тесты для JSONFormatter и структурированного логирования API."""

from __future__ import annotations

import json
import logging
from typing import Any
from unittest.mock import MagicMock

from api.server import APIServer
from logger_config import JSONFormatter, set_structured_api_logging


class TestJSONFormatter:
    """Тесты JSON-форматтера логов."""

    def test_json_formatter_standard_record(self) -> None:
        """Стандартная запись лога форматируется в валидный JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="video_recorder.test",
            level=logging.INFO,
            pathname="api/routes.py",
            lineno=42,
            msg="Test message %s",
            args=("hello",),
            exc_info=None,
        )
        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "INFO"
        assert data["logger"] == "video_recorder.test"
        assert data["message"] == "Test message hello"
        assert "timestamp" in data

    def test_json_formatter_with_extra_fields(self) -> None:
        """Дополнительные поля (trace_id, request_id, latency_ms) включаются в JSON."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="video_recorder.api",
            level=logging.INFO,
            pathname="api/server.py",
            lineno=100,
            msg="API request",
            args=(),
            exc_info=None,
        )
        record.trace_id = "trace-12345"
        record.request_id = "req-12345"
        record.client_ip = "127.0.0.1"
        record.method = "GET"
        record.path = "/api/v1/status"
        record.status_code = 200
        record.latency_ms = 12.34

        output = formatter.format(record)
        data = json.loads(output)

        assert data["trace_id"] == "trace-12345"
        assert data["request_id"] == "req-12345"
        assert data["client_ip"] == "127.0.0.1"
        assert data["method"] == "GET"
        assert data["path"] == "/api/v1/status"
        assert data["status_code"] == 200
        assert data["latency_ms"] == 12.34

    def test_json_formatter_with_exception(self) -> None:
        """Исключение форматируется в поле exception."""
        formatter = JSONFormatter()
        try:
            raise ValueError("Something went wrong")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="video_recorder.api",
            level=logging.ERROR,
            pathname="api/routes.py",
            lineno=50,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        assert data["level"] == "ERROR"
        assert "ValueError: Something went wrong" in data["exception"]


class TestStructuredLoggingIntegration:
    """Тесты интеграции структурированного логирования с APIServer."""

    def test_x_trace_id_response_header(self, tmp_path: Any) -> None:
        """Каждый ответ API содержит заголовок X-Trace-ID."""
        from api.routes import register_routes

        server = APIServer(
            host="127.0.0.1",
            port=5000,
            structured_logs=True,
            state_persistence=MagicMock(),
        )
        register_routes(server.app, server)
        client = server.app.test_client()

        response = client.get("/health")
        assert response.status_code == 200
        assert "X-Trace-ID" in response.headers
        assert "X-Request-ID" in response.headers
        assert (
            response.headers["X-Trace-ID"] == response.headers["X-Request-ID"]
        )

    def test_set_structured_api_logging_toggle(self) -> None:
        """Переключение режима логирования не вызывает ошибок."""
        set_structured_api_logging(True)
        set_structured_api_logging(False)
