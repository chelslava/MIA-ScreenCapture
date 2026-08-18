"""
Unit-тесты для маршрутов API постобработки записей (api/routes_post_processing.py, Issue #118)
=============================================================================================
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_post_processing_api_key_123"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server_post_processing() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestPostProcessingRoutes:
    """Тестирование REST API эндпоинтов /api/v1/post-processing/*."""

    def test_get_config_success(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        mock_cfg = {"enabled": True, "transcode_enabled": False}
        server.set_callback("get_post_processing_config", lambda: mock_cfg)

        resp = client.get("/api/v1/post-processing/config", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["enabled"] is True

    def test_update_config_success(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        server.set_callback(
            "update_post_processing_config",
            lambda d: {"success": True, "config": d},
        )

        payload = {
            "enabled": True,
            "compress_enabled": True,
            "compress_crf": 25,
        }
        resp = client.put(
            "/api/v1/post-processing/config", json=payload, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["config"]["compress_crf"] == 25

    def test_update_config_validation_error(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        # CRF > 51 невалиден
        payload = {"compress_crf": 999}
        resp = client.put(
            "/api/v1/post-processing/config", json=payload, headers=headers
        )
        assert resp.status_code == 400

    def test_get_status_success(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        mock_status = {
            "is_running": False,
            "last_result": {"status": "completed"},
        }
        server.set_callback("get_post_processing_status", lambda: mock_status)

        resp = client.get("/api/v1/post-processing/status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["last_result"]["status"] == "completed"

    def test_run_post_processing_success(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        server.set_callback(
            "run_post_processing",
            lambda file_path, params: {
                "success": True,
                "file_path": file_path,
            },
        )

        payload = {"file_path": "C:/videos/recording.mp4"}
        resp = client.post(
            "/api/v1/post-processing/run", json=payload, headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_get_recording_post_processing_success(
        self, api_server_post_processing: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_post_processing
        mock_status = {"is_running": False, "last_result": None}
        server.set_callback("get_post_processing_status", lambda: mock_status)

        resp = client.get(
            "/api/v1/recording/rec_123/post-processing", headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["recording_id"] == "rec_123"
