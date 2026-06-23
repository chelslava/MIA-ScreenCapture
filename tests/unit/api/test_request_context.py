"""Тесты единого request-контекста API."""

from flask import Flask, g

from api.request_context import ensure_request_context


class TestRequestContext:
    """Проверки формирования request_id/trace_id/client_ip."""

    def test_uses_request_id_header_when_present(self) -> None:
        """При наличии `X-Request-ID` он должен использоваться как базовый."""
        app = Flask(__name__)

        with app.test_request_context(
            "/health",
            headers={"X-Request-ID": "req-123"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        ):
            context = ensure_request_context()

            assert context.request_id == "req-123"
            assert context.trace_id == "req-123"
            assert context.client_ip == "127.0.0.1"
            assert g.request_id == "req-123"
            assert g.trace_id == "req-123"
            assert g.client_ip == "127.0.0.1"

    def test_generates_request_id_once_without_header(self) -> None:
        """Без заголовка должен генерироваться стабильный id в рамках запроса."""
        app = Flask(__name__)

        with app.test_request_context(
            "/api/v1/status",
            environ_base={"REMOTE_ADDR": "10.0.0.2"},
        ):
            first = ensure_request_context()
            second = ensure_request_context()

            assert first.request_id
            assert first.trace_id == first.request_id
            assert second.request_id == first.request_id
            assert second.trace_id == first.trace_id
            assert second.client_ip == "10.0.0.2"
