"""Unit-тесты для REST API эндпоинта метрик записи (#114)."""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_metrics_api_key_12345"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestRecordingMetricsRoute:
    """Тесты эндпоинта GET /api/v1/recording/metrics."""

    def test_get_metrics_success(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server
        mock_metrics = {
            "actual_fps": 29.85,
            "target_fps": 30,
            "jitter_ms": 1.25,
            "frames_dropped": 0,
            "encode_latency_ms": 3.45,
            "buffer_fill_percent": 0.0,
            "total_frames": 120,
        }
        server.set_callback("recording_metrics", lambda: mock_metrics)

        response = client.get("/api/v1/recording/metrics", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["actual_fps"] == 29.85
        assert json_data["data"]["target_fps"] == 30
        assert json_data["data"]["jitter_ms"] == 1.25
        assert json_data["data"]["total_frames"] == 120

    def test_get_metrics_alias_success(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server
        mock_metrics = {
            "actual_fps": 60.0,
            "target_fps": 60,
            "jitter_ms": 0.5,
            "frames_dropped": 1,
            "encode_latency_ms": 2.1,
            "buffer_fill_percent": 5.0,
            "total_frames": 300,
        }
        server.set_callback("recording_metrics", lambda: mock_metrics)

        response = client.get("/api/v1/metrics", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["actual_fps"] == 60.0

    def test_get_metrics_requires_auth(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        _, client, _ = api_server
        response = client.get("/api/v1/recording/metrics")
        assert response.status_code in (401, 403)

    def test_get_metrics_internal_error_when_no_callback(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        _, client, headers = api_server
        response = client.get("/api/v1/recording/metrics", headers=headers)
        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data["success"] is False
