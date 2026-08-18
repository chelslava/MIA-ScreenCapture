"""
Unit-тесты для маршрутов API профилей записи (api/routes_profiles.py)
"""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_profiles_api_key_12345"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server_with_profiles() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestProfilesRoutes:
    """Тестирование REST API эндпоинтов /api/v1/profiles."""

    def test_get_profiles_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        mock_profiles = [
            {"id": "default", "name": "Стандартный", "is_default": True},
            {"id": "gaming", "name": "Игровой", "is_default": False},
        ]
        server.set_callback("get_profiles", lambda: mock_profiles)

        response = client.get("/api/v1/profiles", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert len(json_data["data"]) == 2

    def test_get_profile_by_id_found(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        profile_data = {
            "id": "gaming",
            "name": "Игровой",
            "video": {"fps": 60},
        }
        server.set_callback(
            "get_profile",
            lambda pid: profile_data if pid == "gaming" else None,
        )

        response = client.get("/api/v1/profiles/gaming", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["id"] == "gaming"

    def test_get_profile_by_id_not_found(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback("get_profile", lambda pid: None)

        response = client.get(
            "/api/v1/profiles/unknown_profile", headers=headers
        )
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data["success"] is False

    def test_create_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "create_profile",
            lambda data: {
                "success": True,
                "profile": {"id": "new_123", **data},
            },
        )

        payload = {
            "name": "Новый 4K",
            "description": "Описание",
            "icon": "🚀",
            "video": {"fps": 60, "bitrate": "8M"},
            "is_default": False,
        }
        response = client.post(
            "/api/v1/profiles", json=payload, headers=headers
        )
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["id"] == "new_123"
        assert json_data["data"]["name"] == "Новый 4K"

    def test_create_profile_validation_error(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        response = client.post(
            "/api/v1/profiles", json={"name": ""}, headers=headers
        )
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data["success"] is False

    def test_update_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "update_profile",
            lambda pid, data: {
                "success": True,
                "profile": {"id": pid, "name": data.get("name")},
            },
        )

        response = client.put(
            "/api/v1/profiles/p1",
            json={"name": "Обновленный"},
            headers=headers,
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["name"] == "Обновленный"

    def test_update_profile_not_found(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "update_profile",
            lambda pid, data: {
                "success": False,
                "error": "Профиль не найден",
            },
        )

        response = client.put(
            "/api/v1/profiles/missing",
            json={"name": "Новое имя"},
            headers=headers,
        )
        assert response.status_code == 404
        json_data = response.get_json()
        assert json_data["success"] is False

    def test_delete_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback("delete_profile", lambda pid: {"success": True})

        response = client.delete("/api/v1/profiles/custom_p", headers=headers)
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True

    def test_delete_profile_builtin_rejected(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "delete_profile",
            lambda pid: {
                "success": False,
                "error": "Нельзя удалить встроенный системный профиль",
            },
        )

        response = client.delete("/api/v1/profiles/default", headers=headers)
        assert response.status_code == 400
        json_data = response.get_json()
        assert json_data["success"] is False

    def test_apply_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "apply_profile",
            lambda pid: {
                "success": True,
                "applied_profile": {"id": pid, "name": "Игровой"},
            },
        )

        response = client.post(
            "/api/v1/profiles/gaming/apply", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True

    def test_apply_profile_not_found(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "apply_profile",
            lambda pid: {"success": False, "error": "Профиль не найден"},
        )

        response = client.post(
            "/api/v1/profiles/missing/apply", headers=headers
        )
        assert response.status_code == 404

    def test_export_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "export_profile",
            lambda pid: {
                "schema": "mia.profile.v1",
                "profile": {"id": pid, "name": "Экспорт"},
            },
        )

        response = client.get(
            "/api/v1/profiles/gaming/export", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        assert json_data["data"]["schema"] == "mia.profile.v1"

    def test_import_profile_success(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        server.set_callback(
            "import_profile",
            lambda data: {
                "success": True,
                "profile": {"id": "imp_1", "name": "Импортированный"},
            },
        )

        payload = {
            "schema": "mia.profile.v1",
            "profile": {"name": "Импортированный", "video": {"fps": 60}},
        }
        response = client.post(
            "/api/v1/profiles/import", json=payload, headers=headers
        )
        assert response.status_code == 201
        json_data = response.get_json()
        assert json_data["success"] is True

    def test_start_recording_with_profile_id(
        self, api_server_with_profiles: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        server, client, headers = api_server_with_profiles
        profile_data = {
            "id": "gaming",
            "name": "Игровой",
            "video": {"fps": 60, "codec": "libx264", "bitrate": "8M"},
            "audio": {"record_mic": False, "record_system": True},
            "capture": {"area_type": "full"},
        }
        server.set_callback("get_profile", lambda pid: profile_data)

        started_params: dict[str, Any] = {}

        def mock_start(params: dict[str, Any]) -> dict[str, Any]:
            nonlocal started_params
            started_params = params
            return {"success": True, "output_path": "recording.mp4"}

        server.set_callback("start", mock_start)

        response = client.post(
            "/api/v1/start",
            json={"profile_id": "gaming"},
            headers=headers,
        )
        assert response.status_code == 200
        assert started_params["fps"] == 60
        assert started_params["bitrate"] == "8M"
        assert started_params["audio"] == "system"
        assert started_params["area"] == "full"
