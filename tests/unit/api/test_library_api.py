"""
Unit-тесты для REST API библиотеки записей (api/routes_library.py, Issue #119).
==============================================================================
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_library_api_key_123"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server_library() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    assert server.app is not None
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestLibraryRoutes:
    """Тестирование REST API эндпоинтов /api/v1/library/*."""

    def test_list_library_items_success(
        self, api_server_library: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_library
        mock_items = [
            {"filename": "video1.mp4", "duration_sec": 12.0, "tags": ["tag1"]}
        ]
        server.set_callback("get_library_items", lambda **kwargs: mock_items)

        resp = client.get(
            "/api/v1/library?query=video&tag=tag1", headers=headers
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert len(data["data"]) == 1
        assert data["data"][0]["filename"] == "video1.mp4"

    def test_list_library_tags_success(
        self, api_server_library: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_library
        server.set_callback("get_library_tags", lambda: ["tag1", "tag2"])

        resp = client.get("/api/v1/library/tags", headers=headers)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["data"] == ["tag1", "tag2"]

    def test_add_library_tag_success(
        self, api_server_library: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_library
        server.set_callback("add_library_tag", lambda path, tag: True)

        resp = client.post(
            "/api/v1/library/tags",
            json={"path": "/path/to/video.mp4", "tag": "test_tag"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_remove_library_tag_success(
        self, api_server_library: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_library
        server.set_callback("remove_library_tag", lambda path, tag: True)

        resp = client.delete(
            "/api/v1/library/tags",
            json={"path": "/path/to/video.mp4", "tag": "test_tag"},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True

    def test_delete_library_recording_success(
        self, api_server_library: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_library
        server.set_callback(
            "delete_library_recording", lambda path, delete_file: True
        )

        resp = client.delete(
            "/api/v1/library/recording",
            json={"path": "/path/to/video.mp4", "delete_file": True},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
