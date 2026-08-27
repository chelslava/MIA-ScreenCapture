"""
Unit-тесты для REST API облачной синхронизации (api/routes_cloud.py, Issue #54).
================================================================================
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_cloud_api_key_123"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server_cloud() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    assert server.app is not None
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestCloudRoutes:
    """Тестирование REST API эндпоинтов /api/v1/cloud/*."""

    def test_get_cloud_status_success(
        self, api_server_cloud: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_cloud
        mock_status = {
            "provider": "s3",
            "is_configured": True,
            "queue_size": 0,
            "sync_status": {},
        }
        server.set_callback("get_cloud_status", lambda: mock_status)

        resp = client.get("/api/v1/cloud/status", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["provider"] == "s3"

    def test_configure_cloud_success(
        self, api_server_cloud: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_cloud
        server.set_callback("configure_cloud", lambda **kwargs: True)

        resp = client.post(
            "/api/v1/cloud/config",
            json={
                "provider": "s3",
                "credentials": {"bucket": "my-bucket"},
                "auto_sync": True,
            },
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["provider"] == "s3"

    def test_test_cloud_connection_success(
        self, api_server_cloud: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_cloud
        server.set_callback("test_cloud_connection", lambda: True)

        resp = client.post("/api/v1/cloud/test", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["connected"] is True

    def test_sync_cloud_files_success(
        self, api_server_cloud: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_cloud
        server.set_callback("queue_cloud_sync", lambda p: True)

        resp = client.post(
            "/api/v1/cloud/sync",
            json={"file_paths": ["/path/1.mp4", "/path/2.mp4"]},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["queued"] == 2
