"""Unit-тесты для REST API эндпоинта статуса финализации (#151)."""

from __future__ import annotations

from typing import Any

import pytest

from api.routes import register_routes
from api.server import APIServer

API_KEY = "test_finalization_api_key_12345"
AUTH_HEADERS = {"X-API-Key": API_KEY}


@pytest.fixture
def api_server() -> tuple[APIServer, Any, dict[str, str]]:
    """Создает тестовый APIServer с авторизацией и зарегистрированными маршрутами."""
    server = APIServer(api_key=API_KEY)
    server.app.config["TESTING"] = True
    register_routes(server.app, server)
    client = server.app.test_client()
    return server, client, AUTH_HEADERS


class TestFinalizationStatusRoute:
    """Тесты эндпоинта GET /api/v1/recording/finalization-status."""

    def test_active_finalization(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        """Активная финализация возвращает прогресс и ETA."""
        server, client, headers = api_server
        server.set_callback(
            "finalization_status",
            lambda: {
                "active": True,
                "percent": 42.5,
                "stage": "Объединение видео",
                "elapsed_s": 12.3,
                "eta_s": 16.7,
            },
        )

        response = client.get(
            "/api/v1/recording/finalization-status", headers=headers
        )
        assert response.status_code == 200
        json_data = response.get_json()
        assert json_data["success"] is True
        data = json_data["data"]
        assert data["active"] is True
        assert data["percent"] == 42.5
        assert data["stage"] == "Объединение видео"
        assert data["elapsed_s"] == 12.3
        assert data["eta_s"] == 16.7

    def test_completed_finalization(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        """Завершённая финализация: 100%, ETA отсутствует."""
        server, client, headers = api_server
        server.set_callback(
            "finalization_status",
            lambda: {
                "active": True,
                "percent": 100.0,
                "stage": "Завершено",
                "elapsed_s": 30.0,
                "eta_s": None,
            },
        )

        response = client.get(
            "/api/v1/recording/finalization-status", headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["percent"] == 100.0
        assert data["eta_s"] is None

    def test_no_recording_idle_tracker(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        """Запись не идёт: трекер пуст, timing отсутствует."""
        server, client, headers = api_server
        server.set_callback(
            "finalization_status",
            lambda: {
                "active": False,
                "percent": 0.0,
                "stage": "",
                "elapsed_s": None,
                "eta_s": None,
            },
        )

        response = client.get(
            "/api/v1/recording/finalization-status", headers=headers
        )
        assert response.status_code == 200
        data = response.get_json()["data"]
        assert data["active"] is False
        assert data["elapsed_s"] is None
        assert data["eta_s"] is None

    def test_requires_auth(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        """Без API-ключа доступ запрещён."""
        _, client, _ = api_server
        response = client.get("/api/v1/recording/finalization-status")
        assert response.status_code in (401, 403)

    def test_internal_error_when_no_callback(
        self, api_server: tuple[APIServer, Any, dict[str, str]]
    ) -> None:
        """Без зарегистрированного колбэка — внутренняя ошибка."""
        _, client, headers = api_server
        response = client.get(
            "/api/v1/recording/finalization-status", headers=headers
        )
        assert response.status_code == 500
        json_data = response.get_json()
        assert json_data["success"] is False
