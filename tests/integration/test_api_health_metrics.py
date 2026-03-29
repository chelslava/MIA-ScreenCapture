"""Интеграционные тесты health и observability API."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from api.routes import register_routes
from api.server import APIServer
from api.websocket import WebSocketManager

TEST_API_KEY = "test-api-key-for-integration-tests-12345"


@pytest.fixture
def api_server() -> Generator[APIServer, None, None]:
    """Создаёт API сервер с готовыми route handlers."""
    server = APIServer(
        host="127.0.0.1",
        port=5012,
        api_key=TEST_API_KEY,
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

    websocket_manager = WebSocketManager()
    websocket_manager.publish(
        {
            "type": "started",
            "timestamp": "2026-03-23T12:00:00+00:00",
            "data": {"output_path": "/tmp/test_recording.mp4"},
        }
    )
    server.set_websocket_manager(websocket_manager)
    register_routes(server.app, server)
    server.app.config["TESTING"] = True

    yield server
    server.stop()


def _make_client(
    api_server: APIServer,
    *,
    authenticated: bool,
) -> FlaskClient:
    """Создаёт тестовый клиент с нужным режимом авторизации."""
    client = api_server.app.test_client()
    if authenticated:
        client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


def _prime_observability(
    api_server: APIServer,
) -> tuple[FlaskClient, FlaskClient]:
    """Создаёт клиентов и генерирует стабильный набор запросов."""
    auth_client = _make_client(api_server, authenticated=True)
    unauth_client = _make_client(api_server, authenticated=False)

    auth_client.get("/api/status", headers={"X-Request-ID": "status-1"})
    unauth_client.get("/health", headers={"X-Request-ID": "health-1"})
    auth_client.get("/api/status", headers={"X-Request-ID": "status-2"})

    return auth_client, unauth_client


class TestAPIHealthMetrics:
    """Проверяет health и observability payload сервера."""

    def test_health_returns_extended_payload_without_auth(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет расширенный health payload без аутентификации."""
        unauth_client = _make_client(api_server, authenticated=False)

        response = unauth_client.get(
            "/health",
            headers={"X-Request-ID": "health-request-001"},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "health-request-001"

        payload = response.get_json()
        assert payload["status"] == "ok"
        assert isinstance(payload["timestamp"], str)
        assert payload["version"] == api_server._version
        assert payload["uptime_seconds"] >= 0

        websocket = payload["websocket"]
        assert websocket["transport_ready"] is True
        assert websocket["buffered_events"] == 1
        assert websocket["events_published_total"] == 1
        assert websocket["attached_to_event_bus"] is False

    def test_observability_metrics_reflect_request_traffic(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет snapshot метрик после нескольких запросов."""
        auth_client, _ = _prime_observability(api_server)

        response = auth_client.get(
            "/api/v1/observability/metrics",
            headers={"X-Request-ID": "metrics-request-001"},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "metrics-request-001"

        payload = response.get_json()["data"]
        assert payload["requests_total"] == 3
        assert payload["requests_inflight"] == 1
        assert payload["errors_total"] == 0
        assert payload["status_codes"] == {"200": 3}
        assert payload["methods"] == {"GET": 3}
        assert payload["latency_ms"]["count"] == 3
        assert payload["idempotency_store_size"] == 0
        assert payload["top_paths"][0] == {"path": "/api/status", "count": 2}
        assert payload["top_paths"][1] == {"path": "/health", "count": 1}
        assert payload["resources"]["rss_mb"] >= 0
        assert payload["resources"]["threads"] >= 1
        assert isinstance(payload["generated_at"], str)

    def test_observability_baseline_contains_slo_snapshot(
        self,
        api_server: APIServer,
    ) -> None:
        """Проверяет baseline SLO после нескольких запросов."""
        auth_client, _ = _prime_observability(api_server)

        response = auth_client.get(
            "/api/v1/observability/baseline",
            headers={"X-Request-ID": "baseline-request-001"},
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "baseline-request-001"

        payload = response.get_json()["data"]
        assert payload["sample_size"] == 3
        assert payload["slo_targets"] == {
            "p95_latency_ms": 100.0,
            "error_rate_percent": 1.0,
        }
        assert payload["current"]["error_rate_percent"] == 0.0
        assert payload["current"]["p95_latency_ms"] >= 0
        assert payload["current"]["requests_per_second"] > 0
        assert payload["current"]["rss_mb"] >= 0
        assert payload["meets_targets"]["error_rate"] is True
        assert isinstance(payload["meets_targets"]["latency"], bool)
        assert isinstance(payload["generated_at"], str)
