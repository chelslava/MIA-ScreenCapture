"""Интеграционные тесты обработки ошибок API."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from api.routes import register_routes
from api.server import APIServer
from api.websocket import WebSocketManager

TEST_API_KEY = "test-api-key-for-integration-tests-12345"


@pytest.fixture
def api_server() -> Generator[APIServer, None, None]:
    """Создаёт API сервер с callback'ами для проверок ошибок."""
    server = APIServer(
        host="127.0.0.1",
        port=5013,
        api_key=TEST_API_KEY,
    )
    server.set_callback(
        "start",
        MagicMock(
            return_value={
                "success": True,
                "output_path": "/tmp/test_recording.mp4",
            }
        ),
    )
    server.set_callback(
        "status",
        MagicMock(
            return_value={
                "is_recording": False,
                "is_paused": False,
                "elapsed_time": 0,
                "current_file": None,
            }
        ),
    )
    server.set_websocket_manager(WebSocketManager())
    register_routes(server.app, server)
    server.app.config["TESTING"] = True

    yield server
    server.stop()


def _make_client(
    api_server: APIServer,
    *,
    authenticated: bool = True,
) -> FlaskClient:
    """Создаёт тестовый клиент с опциональной авторизацией."""
    client = api_server.app.test_client()
    if authenticated:
        client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


def _assert_internal_error_contract(response: Any) -> dict[str, Any]:
    """Проверяет единый контракт внутренней ошибки."""
    data = response.get_json()
    assert data["success"] is False
    assert data["trace_id"]
    assert response.headers["X-Request-ID"] == data["trace_id"]

    error = data["error"]
    assert error["code"] == "internal_error"
    assert error["message"] == "Внутренняя ошибка сервера"
    assert error["details"] is None
    return data


class TestAPIErrorHandling:
    """Проверяет безопасную обработку исключений в server/routes."""

    def test_health_returns_500_when_websocket_stats_fails(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет 500 на health, если сбор websocket stats падает."""
        manager = api_server.get_websocket_manager()
        assert manager is not None

        manager.get_stats = MagicMock(
            side_effect=RuntimeError("websocket failure")
        )

        client = _make_client(api_server, authenticated=False)
        response = client.get(
            "/health",
            headers={"X-Request-ID": "health-error-001"},
        )

        assert response.status_code == 500
        data = _assert_internal_error_contract(response)
        assert response.headers["X-Request-ID"] == "health-error-001"
        assert data["error"]["message"] == "Внутренняя ошибка сервера"

    def test_start_returns_internal_error_when_callback_raises(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет безопасный ответ при падении start callback."""
        api_server.set_callback(
            "start",
            MagicMock(side_effect=RuntimeError("start failed")),
        )
        client = _make_client(api_server)

        response = client.post(
            "/api/start",
            json={},
            headers={"X-Request-ID": "start-error-001"},
        )

        assert response.status_code == 500
        data = _assert_internal_error_contract(response)
        assert data["error"]["message"] == "Внутренняя ошибка сервера"

    def test_metrics_returns_internal_error_when_collection_fails(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет 500 на metrics при исключении в server method."""
        api_server.get_observability_metrics = MagicMock(
            side_effect=RuntimeError("metrics failed")
        )
        client = _make_client(api_server)

        response = client.get(
            "/api/v1/observability/metrics",
            headers={"X-Request-ID": "metrics-error-001"},
        )

        assert response.status_code == 500
        _assert_internal_error_contract(response)

    def test_baseline_returns_internal_error_when_collection_fails(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет 500 на baseline при исключении в server method."""
        api_server.get_observability_baseline = MagicMock(
            side_effect=RuntimeError("baseline failed")
        )
        client = _make_client(api_server)

        response = client.get(
            "/api/v1/observability/baseline",
            headers={"X-Request-ID": "baseline-error-001"},
        )

        assert response.status_code == 500
        _assert_internal_error_contract(response)
