"""Интеграционные тесты жизненного цикла API-сервера."""

from __future__ import annotations

import threading
from collections.abc import Generator
from unittest.mock import MagicMock

import pytest

from api.server import APIServer

TEST_API_KEY = "test-api-key-for-integration-tests-12345"


class _FakeWsgiServer:
    """Фейковый waitress-сервер для проверки жизненного цикла."""

    def __init__(self) -> None:
        self.started = threading.Event()
        self.closed = threading.Event()
        self.close_calls = 0

    def run(self) -> None:
        self.started.set()
        self.closed.wait(timeout=1.0)

    def close(self) -> None:
        self.close_calls += 1
        self.closed.set()


@pytest.fixture
def api_server() -> Generator[APIServer, None, None]:
    """Создаёт API сервер с предсказуемым API-ключом."""
    server = APIServer(
        host="127.0.0.1",
        port=5011,
        api_key=TEST_API_KEY,
    )
    yield server
    server.stop()


def _prepare_started_server(
    api_server: APIServer,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[MagicMock, _FakeWsgiServer]:
    """Подменяет waitress и отключает bind-проверку."""
    fake_wsgi_server = _FakeWsgiServer()
    create_server_mock = MagicMock(return_value=fake_wsgi_server)

    monkeypatch.setattr("api.server.create_server", create_server_mock)
    monkeypatch.setattr(api_server, "_validate_bind_address", lambda: None)
    return create_server_mock, fake_wsgi_server


class TestAPIServerLifecycle:
    """Проверяет запуск, остановку и состояние API-сервера."""

    def test_start_and_stop_updates_running_state(
        self,
        api_server: APIServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Проверяет успешный старт и корректную остановку сервера."""
        create_server_mock, fake_wsgi_server = _prepare_started_server(
            api_server,
            monkeypatch,
        )

        assert api_server.start() is True
        assert fake_wsgi_server.started.wait(timeout=1.0) is True
        assert api_server.is_running() is True

        status = api_server.get_status()
        assert status["running"] is True
        assert status["host"] == "127.0.0.1"
        assert status["port"] == 5011
        assert status["url"] == "http://127.0.0.1:5011"
        assert status["api_key"] != TEST_API_KEY
        assert status["api_key"].startswith(TEST_API_KEY[:4])
        assert status["api_key"].endswith(TEST_API_KEY[-4:])
        assert "****" in status["api_key"]
        assert status["api_key_set"] is True

        assert api_server._server_thread is not None
        assert api_server._server_thread.is_alive() is True

        api_server.stop()

        assert fake_wsgi_server.close_calls == 1
        assert api_server.is_running() is False
        assert api_server._server_thread is not None
        assert api_server._server_thread.is_alive() is False
        create_server_mock.assert_called_once_with(
            api_server.app,
            host="127.0.0.1",
            port=5011,
            threads=4,
            clear_untrusted_proxy_headers=True,
        )

    def test_start_returns_false_when_server_is_already_running(
        self,
        api_server: APIServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Проверяет отказ от повторного запуска активного сервера."""
        _, fake_wsgi_server = _prepare_started_server(api_server, monkeypatch)

        assert api_server.start() is True
        assert fake_wsgi_server.started.wait(timeout=1.0) is True
        assert api_server.start() is False

        api_server.stop()

    def test_start_returns_false_when_bind_validation_fails(
        self,
        api_server: APIServer,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Проверяет fail-fast при ошибке bind-проверки."""
        create_server_mock = MagicMock()

        monkeypatch.setattr("api.server.create_server", create_server_mock)
        monkeypatch.setattr(
            api_server,
            "_validate_bind_address",
            MagicMock(side_effect=OSError("Address already in use")),
        )

        assert api_server.start() is False
        assert api_server.is_running() is False
        assert api_server._server_thread is None
        create_server_mock.assert_not_called()

    @pytest.mark.parametrize(
        ("origin", "expected_allowed_origin"),
        [
            ("http://localhost:3000", "http://localhost:3000"),
            ("http://127.0.0.1:8080", "http://127.0.0.1:8080"),
            ("https://localhost", "https://localhost"),
            ("https://evil.example", None),
        ],
    )
    def test_cors_actual_request_origin_filtering(
        self,
        api_server: APIServer,
        origin: str,
        expected_allowed_origin: str | None,
    ) -> None:
        """Проверяет CORS-заголовки для actual request по allowlist."""
        assert api_server.app is not None
        client = api_server.app.test_client()

        response = client.get("/health", headers={"Origin": origin})

        assert response.status_code == 200
        assert (
            response.headers.get("Access-Control-Allow-Origin")
            == expected_allowed_origin
        )

    def test_cors_preflight_allows_localhost_origin(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет CORS preflight для разрешённого localhost origin."""
        assert api_server.app is not None
        client = api_server.app.test_client()

        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "Content-Type,X-Request-ID",
            },
        )

        assert response.status_code == 200
        assert (
            response.headers.get("Access-Control-Allow-Origin")
            == "http://localhost:3000"
        )
        assert "GET" in response.headers.get(
            "Access-Control-Allow-Methods", ""
        )
        allow_headers = response.headers.get(
            "Access-Control-Allow-Headers", ""
        )
        assert "Content-Type" in allow_headers
        assert "X-Request-ID" in allow_headers

    def test_cors_preflight_rejects_untrusted_origin(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет отсутствие CORS-доступа для чужого origin."""
        assert api_server.app is not None
        client = api_server.app.test_client()

        response = client.options(
            "/health",
            headers={
                "Origin": "https://evil.example",
                "Access-Control-Request-Method": "GET",
            },
        )

        assert response.status_code == 200
        assert "Access-Control-Allow-Origin" not in response.headers
