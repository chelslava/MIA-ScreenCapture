"""
Unit-тесты для маршрутов API плагинов (api/routes_plugins.py, Issue #124)
========================================================================
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_plugins_api_key_123"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server_plugins() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    assert server.app is not None
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestPluginsRoutes:
    """Тестирование REST API эндпоинтов /api/v1/plugins/*."""

    def test_list_plugins_success(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        mock_plugins = [
            {"name": "test_plugin", "version": "1.0.0", "status": "enabled"}
        ]
        server.set_callback("get_plugins", lambda: mock_plugins)

        resp = client.get("/api/v1/plugins", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["name"] == "test_plugin"

    def test_get_plugin_info_success(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        mock_info = {
            "name": "my_plugin",
            "version": "2.0.0",
            "settings_schema": {"type": "object"},
        }
        server.set_callback(
            "get_plugin_info",
            lambda name: mock_info if name == "my_plugin" else None,
        )

        resp = client.get("/api/v1/plugins/my_plugin", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"]["version"] == "2.0.0"

    def test_get_plugin_info_not_found(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        server.set_callback("get_plugin_info", lambda name: None)

        resp = client.get("/api/v1/plugins/non_existent", headers=headers)
        assert resp.status_code == 404
        data = resp.get_json()
        assert data["success"] is False

    def test_enable_plugin_success(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        server.set_callback("enable_plugin", lambda name: True)

        resp = client.post("/api/v1/plugins/my_plugin/enable", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_disable_plugin_success(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        server.set_callback("disable_plugin", lambda name: True)

        resp = client.post(
            "/api/v1/plugins/my_plugin/disable", headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_configure_plugin_success(
        self, api_server_plugins: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_plugins
        server.set_callback("configure_plugin", lambda name, cfg: True)

        resp = client.put(
            "/api/v1/plugins/my_plugin/config",
            json={"watermark": "test"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
