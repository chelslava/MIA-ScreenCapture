"""
Интеграционные тесты для API
============================

Тестирует REST API эндпоинты с реальным Flask сервером.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest
from flask import Flask, jsonify
from flask.testing import FlaskClient

from api.auth import init_api_auth
from api.rate_limiter import RateLimitConfig, init_rate_limiter
from api.routes import register_routes
from api.server import APIServer
from api.websocket import WebSocketManager

# Тестовый API ключ для интеграционных тестов
TEST_API_KEY = "test-api-key-for-integration-tests-12345"


def assert_error_contract(response, expected_code: str):
    """Проверяет единый контракт ошибки API."""
    data = response.get_json()
    assert data["success"] is False
    assert isinstance(data["trace_id"], str)
    assert data["trace_id"]
    assert response.headers.get("X-Request-ID")

    error = data["error"]
    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert "details" in error
    return data


@pytest.fixture
def mock_callbacks() -> dict[str, MagicMock]:
    """
    Создание mock функций обратного вызова.

    Returns:
        Словарь с mock функциями для каждого действия
    """
    return {
        "status": MagicMock(
            return_value={
                "is_recording": False,
                "is_paused": False,
                "elapsed_time": 0,
                "current_file": None,
            }
        ),
        "start": MagicMock(
            return_value={
                "success": True,
                "output_path": "/tmp/test_recording.mp4",
            }
        ),
        "stop": MagicMock(
            return_value={
                "success": True,
                "output_path": "/tmp/test_recording.mp4",
                "duration": 10.5,
            }
        ),
        "pause": MagicMock(return_value={"success": True, "is_paused": True}),
        "resume": MagicMock(
            return_value={"success": True, "is_paused": False}
        ),
        "recordings": MagicMock(
            return_value={
                "recordings": [
                    {
                        "path": "/tmp/recording1.mp4",
                        "date": "2026-03-18T10:00:00",
                        "size": 1024000,
                    }
                ]
            }
        ),
        # Исправленные имена callbacks в соответствии с api/routes.py
        "get_schedule": MagicMock(return_value={"tasks": []}),
        "create_schedule": MagicMock(
            return_value={"success": True, "task_id": "test-task-001"}
        ),
        "delete_schedule": MagicMock(return_value={"success": True}),
        "update_schedule": MagicMock(return_value={"success": True}),
        "toggle_schedule": MagicMock(return_value={"success": True}),
        "devices": MagicMock(
            return_value={
                "input": [
                    {"index": 0, "name": "Microphone"},
                    {"index": 1, "name": "Headset"},
                ],
                "output": [{"index": 0, "name": "Speakers"}],
            }
        ),
        "windows": MagicMock(
            return_value={
                "windows": [
                    {
                        "title": "Browser",
                        "x": 0,
                        "y": 0,
                        "width": 1920,
                        "height": 1080,
                    }
                ]
            }
        ),
        "get_config": MagicMock(
            return_value={
                "video": {"fps": 30, "codec": "libx264"},
                "audio": {"sample_rate": 44100},
            }
        ),
        "update_config": MagicMock(return_value={"success": True}),
    }


@pytest.fixture
def test_app(mock_callbacks: dict[str, MagicMock]) -> Flask:
    """
    Создание тестового Flask приложения.

    Args:
        mock_callbacks: Словарь с mock функциями

    Returns:
        Настроенное Flask приложение
    """
    server = APIServer(host="127.0.0.1", port=5001)

    # Инициализация API аутентификации с тестовым ключом
    init_api_auth(server.app, api_key=TEST_API_KEY)

    # Установка mock callbacks
    for action, callback in mock_callbacks.items():
        server.set_callback(action, callback)
    websocket_manager = WebSocketManager()
    websocket_manager.publish(
        {
            "type": "started",
            "timestamp": "2026-03-23T12:00:00+00:00",
            "data": {"output_path": "/tmp/test_recording.mp4"},
        }
    )
    server.set_websocket_manager(websocket_manager)

    # Регистрация маршрутов
    register_routes(server.app, server)

    server.app.config["TESTING"] = True

    return server.app


@pytest.fixture
def rate_limited_app(mock_callbacks: dict[str, MagicMock]) -> Flask:
    """
    Создание Flask приложения с очень низким лимитом для теста 429.
    """
    server = APIServer(host="127.0.0.1", port=5008)
    init_api_auth(server.app, api_key=TEST_API_KEY)
    init_rate_limiter(
        server.app,
        RateLimitConfig(
            requests_per_minute=1,
            requests_per_hour=10,
            burst_limit=1,
            block_duration=60,
            enabled=True,
        ),
    )
    for action, callback in mock_callbacks.items():
        server.set_callback(action, callback)
    server.set_websocket_manager(WebSocketManager())
    register_routes(server.app, server)
    server.app.config["TESTING"] = True
    return server.app


@pytest.fixture
def rate_limited_client(rate_limited_app: Flask) -> FlaskClient:
    client = rate_limited_app.test_client()
    client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


@pytest.fixture
def client(test_app: Flask) -> FlaskClient:
    """
    Создание тестового клиента с авторизацией.

    Args:
        test_app: Flask приложение

    Returns:
        Тестовый клиент с заголовком авторизации
    """
    test_client = test_app.test_client()
    # Добавляем API ключ в environ_base для всех запросов
    test_client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return test_client


@pytest.fixture
def unauth_client(test_app: Flask) -> FlaskClient:
    """
    Создание неавторизованного тестового клиента.

    Используется для тестирования защиты эндпоинтов.

    Args:
        test_app: Flask приложение

    Returns:
        Тестовый клиент без авторизации
    """
    return test_app.test_client()


class TestAPIStatusEndpoint:
    """Тесты для эндпоинта /api/status."""

    def test_get_status_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка успешного получения статуса."""
        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert "is_recording" in data["data"]
        mock_callbacks["status"].assert_called_once()

    def test_get_status_recording(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка статуса во время записи."""
        mock_callbacks["status"].return_value = {
            "is_recording": True,
            "is_paused": False,
            "elapsed_time": 45.2,
            "current_file": "/tmp/recording.mp4",
        }

        response = client.get("/api/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["is_recording"] is True
        assert data["data"]["elapsed_time"] == 45.2


class TestAPIStartEndpoint:
    """Тесты для эндпоинта /api/start."""

    def test_start_recording_default_params(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка запуска записи с параметрами по умолчанию."""
        response = client.post(
            "/api/start", json={}, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["start"].assert_called_once()

    def test_start_recording_with_params(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка запуска записи с пользовательскими параметрами."""
        request_data = {
            "area": "rect",
            "rect": [100, 100, 800, 600],
            "audio": "mic",
            "fps": 60,
            "codec": "libx264",
            "bitrate": "5M",
            "duration": 300,
        }

        response = client.post(
            "/api/start", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # Проверка переданных параметров
        call_args = mock_callbacks["start"].call_args[0][0]
        assert call_args["area"] == "rect"
        assert call_args["fps"] == 60

    def test_start_recording_invalid_fps(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка валидации некорректного FPS."""
        request_data = {
            "fps": 150  # Превышает максимум 120
        }

        response = client.post(
            "/api/start",
            json=request_data,
            content_type="application/json",
            headers={"X-Request-ID": "req-validation-fps"},
        )

        assert response.status_code == 400
        data = assert_error_contract(response, "validation_error")
        assert isinstance(data["error"]["details"], list)
        assert any(
            item.get("field") == "fps" for item in data["error"]["details"]
        )
        assert data["error"]["code"] == "validation_error"

    def test_start_recording_invalid_area(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка валидации некорректной области."""
        request_data = {
            "area": "window"  # Требуется window_title
        }

        response = client.post(
            "/api/start", json=request_data, content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_start_recording_invalid_rect(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка валидации некорректных координат прямоугольника."""
        request_data = {
            "area": "rect",
            "rect": [100, 100, 50, 200],  # x2 < x1
        }

        response = client.post(
            "/api/start", json=request_data, content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False

    def test_start_recording_invalid_bitrate(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка валидации некорректного битрейта."""
        request_data = {"bitrate": "invalid"}

        response = client.post(
            "/api/start", json=request_data, content_type="application/json"
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False


class TestAPIStopEndpoint:
    """Тесты для эндпоинта /api/stop."""

    def test_stop_recording_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка успешной остановки записи."""
        response = client.post("/api/stop")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["stop"].assert_called_once()

    def test_stop_recording_not_recording(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка остановки когда запись не активна."""
        # Примечание: API возвращает 200 даже при неудаче, проверяем success=False
        mock_callbacks["stop"].return_value = {
            "success": False,
            "error": "Нет активной записи",
        }

        response = client.post("/api/stop")

        # API возвращает 200 с success=False в данных
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is False


class TestAPIPauseEndpoint:
    """Тесты для эндпоинта /api/pause."""

    def test_pause_recording_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка успешной паузы записи."""
        response = client.post("/api/pause")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["pause"].assert_called_once()


class TestAPIRecordingsEndpoint:
    """Тесты для эндпоинта /api/recordings."""

    def test_get_recordings_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка получения списка записей."""
        response = client.get("/api/recordings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        mock_callbacks["recordings"].assert_called_once()

    def test_get_recordings_empty(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка пустого списка записей."""
        mock_callbacks["recordings"].return_value = {"recordings": []}

        response = client.get("/api/recordings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["data"]["recordings"] == []


class TestAPIEventsEndpoint:
    """Тесты для эндпоинтов событий."""

    def test_get_recent_events_success(self, client: FlaskClient) -> None:
        response = client.get("/api/events/recent?limit=10")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
        assert data["data"][0]["type"] == "started"
        assert "timestamp" in data["data"][0]
        assert "data" in data["data"][0]
        assert (
            data["data"][0]["data"]["output_path"] == "/tmp/test_recording.mp4"
        )

    def test_get_events_stats_success(self, client: FlaskClient) -> None:
        response = client.get("/api/events/stats")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["transport_ready"] is True
        assert data["data"]["buffered_events"] == 1
        assert "events_published_total" in data["data"]
        assert data["data"]["events_published_total"] == 1
        assert data["data"]["attached_to_event_bus"] is False


class TestAPIObservabilityEndpoints:
    """Тесты observability endpoint'ов."""

    def test_get_observability_metrics_success(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/api/observability/metrics")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        payload = data["data"]
        assert "requests_total" in payload
        assert "requests_inflight" in payload
        assert "latency_ms" in payload
        assert "resources" in payload
        assert "generated_at" in payload

    def test_get_observability_baseline_success(
        self, client: FlaskClient
    ) -> None:
        response = client.get("/api/observability/baseline")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        payload = data["data"]
        assert "slo_targets" in payload
        assert "current" in payload
        assert "meets_targets" in payload


class TestAPIScheduleEndpoints:
    """Тесты для эндпоинтов планировщика."""

    def test_get_schedule_list(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка получения списка задач."""
        response = client.get("/api/schedule")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["get_schedule"].assert_called_once()

    def test_create_schedule_task_once(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка создания разовой задачи."""
        # Используем будущую дату (через 1 час от текущего времени)
        future_datetime = (datetime.now() + timedelta(hours=1)).isoformat()

        request_data = {
            "name": "Test Once Task",
            "trigger": "once",
            "datetime": future_datetime,
            "params": {"area": "full", "fps": 30},
        }

        response = client.post(
            "/api/schedule", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["create_schedule"].assert_called_once()

    def test_create_schedule_task_daily(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка создания ежедневной задачи."""
        request_data = {
            "name": "Test Daily Task",
            "trigger": "daily",
            "time": "09:00",
            "params": {"area_type": "window", "window_title": "Browser"},
        }

        response = client.post(
            "/api/schedule", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_create_schedule_task_weekly(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка создания еженедельной задачи."""
        request_data = {
            "name": "Test Weekly Task",
            "trigger": "weekly",
            "time": "10:00",
            "day_of_week": "0,2,4",
            "params": {},
        }

        response = client.post(
            "/api/schedule", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_create_schedule_task_interval(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка создания интервальной задачи."""
        request_data = {
            "name": "Test Interval Task",
            "trigger": "interval",
            "hours": 2,
            "minutes": 30,
            "params": {},
        }

        response = client.post(
            "/api/schedule", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_delete_schedule_task(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка удаления задачи."""
        response = client.delete("/api/schedule/test-task-001")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["delete_schedule"].assert_called_once()

    def test_toggle_schedule_task(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка переключения активности задачи."""
        request_data = {"enabled": False}

        response = client.post(
            "/api/schedule/test-task-001/toggle",
            json=request_data,
            content_type="application/json",
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


class TestAPIDevicesEndpoint:
    """Тесты для эндпоинта /api/devices."""

    def test_get_devices_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка получения списка устройств."""
        response = client.get("/api/devices")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert "input" in data["data"]
        assert "output" in data["data"]
        mock_callbacks["devices"].assert_called_once()


class TestAPIWindowsEndpoint:
    """Тесты для эндпоинта /api/windows."""

    def test_get_windows_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка получения списка окон."""
        response = client.get("/api/windows")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "data" in data
        assert "windows" in data["data"]
        mock_callbacks["windows"].assert_called_once()


class TestAPIConfigEndpoint:
    """Тесты для эндпоинтов конфигурации."""

    def test_get_config_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка получения конфигурации."""
        response = client.get("/api/config")

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["get_config"].assert_called_once()

    def test_update_config_success(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка обновления конфигурации."""
        request_data = {"video": {"fps": 60}}

        response = client.put(
            "/api/config", json=request_data, content_type="application/json"
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        mock_callbacks["update_config"].assert_called_once_with({"fps": 60})


class TestAPIErrorHandling:
    """Тесты обработки ошибок API."""

    def test_404_error(self, client: FlaskClient):
        """Проверка обработки 404 ошибки."""
        response = client.get(
            "/api/nonexistent",
            headers={"X-Request-ID": "req-404"},
        )

        assert response.status_code == 404
        data = assert_error_contract(response, "not_found")
        assert data["error"]["message"] == "Не найдено"

    def test_invalid_json(self, client: FlaskClient):
        """Проверка обработки некорректного JSON."""
        response = client.post(
            "/api/start", data="invalid json", content_type="application/json"
        )

        assert response.status_code == 400
        data = assert_error_contract(response, "bad_request")
        assert data["error"]["message"] == "Некорректный JSON в теле запроса"
        assert isinstance(data["error"]["message"], str)

    def test_payload_too_large_returns_413(self, client: FlaskClient):
        """Проверка защиты от слишком большого JSON тела запроса."""
        oversized_payload = {"data": "x" * (1024 * 1024 + 1000)}
        response = client.post(
            "/api/start",
            json=oversized_payload,
            content_type="application/json",
        )

        assert response.status_code == 413
        data = assert_error_contract(response, "payload_too_large")
        assert isinstance(data["error"]["message"], str)

    def test_legacy_error_payload_does_not_leak_internal_fields(
        self, client: FlaskClient
    ):
        """Проверка, что legacy error payload не протаскивает внутренние поля."""
        app = client.application

        def legacy_error():
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Legacy failure",
                        "message": "Legacy failure",
                        "debug": "internal-secret",
                        "stacktrace": "traceback content",
                    }
                ),
                400,
            )

        app.add_url_rule(
            "/__legacy-error-test",
            endpoint="legacy_error_test",
            view_func=legacy_error,
        )

        response = client.get("/__legacy-error-test")

        assert response.status_code == 400
        data = assert_error_contract(response, "bad_request")
        assert data["error"]["message"] == "Legacy failure"
        assert data["error"]["details"] is None
        assert "debug" not in data
        assert "stacktrace" not in data["error"]

    def test_callback_returns_error(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ):
        """Проверка обработки ошибки от callback."""
        mock_callbacks["start"].return_value = {
            "success": False,
            "error": "Ошибка запуска записи",
        }

        response = client.post(
            "/api/start",
            json={},
            content_type="application/json",
            headers={"X-Request-ID": "req-start-callback"},
        )

        assert response.status_code == 400
        data = assert_error_contract(response, "bad_request")
        assert data["error"]["message"] == "Ошибка запуска записи"


class TestAPIServerIntegration:
    """Интеграционные тесты APIServer."""

    def test_server_creation(self):
        """Проверка создания сервера."""
        server = APIServer(host="127.0.0.1", port=5002)

        assert server.host == "127.0.0.1"
        assert server.port == 5002
        assert server.app is not None

    def test_set_and_get_callback(self):
        """Проверка установки и получения callback."""
        server = APIServer(host="127.0.0.1", port=5003)

        def test_callback():
            return {"status": "ok"}

        server.set_callback("test", test_callback)

        assert server.get_callback("test") == test_callback
        assert server.get_callback("nonexistent") is None

    def test_multiple_callbacks(self):
        """Проверка установки нескольких callbacks."""
        server = APIServer(host="127.0.0.1", port=5004)

        callbacks = {
            "start": lambda: {"started": True},
            "stop": lambda: {"stopped": True},
            "status": lambda: {"recording": False},
        }

        for action, callback in callbacks.items():
            server.set_callback(action, callback)

        for action, callback in callbacks.items():
            assert server.get_callback(action) == callback


class TestAPIAuthentication:
    """Тесты аутентификации API."""

    def test_protected_endpoint_without_key(self, unauth_client: FlaskClient):
        """Проверка защиты эндпоинта без API ключа."""
        response = unauth_client.get(
            "/api/status",
            headers={"X-Request-ID": "req-401-missing-key"},
        )

        assert response.status_code == 401
        data = assert_error_contract(response, "unauthorized")
        assert data["error"]["message"]

    def test_protected_endpoint_with_invalid_key(
        self, unauth_client: FlaskClient
    ):
        """Проверка защиты эндпоинта с неверным API ключом."""
        unauth_client.environ_base["HTTP_X_API_KEY"] = "invalid-key"
        response = unauth_client.get(
            "/api/status",
            headers={"X-Request-ID": "req-401-invalid-key"},
        )

        assert response.status_code == 401
        assert_error_contract(response, "unauthorized")

    def test_protected_endpoint_with_valid_key(self, client: FlaskClient):
        """Проверка доступа с валидным API ключом."""
        response = client.get("/api/status")

        assert response.status_code == 200

    def test_health_endpoint_no_auth_required(
        self, unauth_client: FlaskClient
    ):
        """Проверка что health эндпоинт не требует аутентификации."""
        response = unauth_client.get("/health")

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data
        assert "websocket" in data
        assert data["websocket"]["transport_ready"] is True

    def test_start_requires_auth(self, unauth_client: FlaskClient):
        """Проверка что /api/start требует аутентификации."""
        response = unauth_client.post(
            "/api/start", json={}, content_type="application/json"
        )

        assert response.status_code == 401

    def test_stop_requires_auth(self, unauth_client: FlaskClient):
        """Проверка что /api/stop требует аутентификации."""
        response = unauth_client.post("/api/stop")

        assert response.status_code == 401

    def test_config_requires_auth(self, unauth_client: FlaskClient):
        """Проверка что /api/config требует аутентификации."""
        response = unauth_client.get("/api/config")

        assert response.status_code == 401

    def test_observability_requires_auth(self, unauth_client: FlaskClient):
        """Проверка что observability endpoint требует аутентификации."""
        response = unauth_client.get("/api/observability/metrics")

        assert response.status_code == 401


class TestAPIRateLimit:
    """Тесты rate limiting на mutating endpoints."""

    def test_start_endpoint_returns_429_on_second_request(
        self,
        rate_limited_client: FlaskClient,
        mock_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверка 429 на повторном POST /api/start."""
        first_response = rate_limited_client.post(
            "/api/start", json={}, content_type="application/json"
        )
        second_response = rate_limited_client.post(
            "/api/start", json={}, content_type="application/json"
        )

        assert first_response.status_code == 200
        assert second_response.status_code == 429
        data = assert_error_contract(second_response, "rate_limited")
        assert data["error"]["details"]["limit_type"] in {"burst", "minute"}
        assert mock_callbacks["start"].call_count == 1

    def test_health_endpoint_stays_available(
        self, rate_limited_client: FlaskClient
    ) -> None:
        """Проверка, что health endpoint не ограничивается rate limiter."""
        response = rate_limited_client.get("/health")

        assert response.status_code == 200


class TestAPIIdempotency:
    """Тесты идемпотентности write-endpoints."""

    def test_start_replays_response_for_same_key_and_payload(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        headers = {"Idempotency-Key": "same-start-key-001"}
        request_data = {"area": "full", "fps": 30}

        first = client.post(
            "/api/start",
            json=request_data,
            content_type="application/json",
            headers=headers,
        )
        second = client.post(
            "/api/start",
            json=request_data,
            content_type="application/json",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 200
        assert second.headers["X-Idempotency-Replayed"] == "true"
        assert first.get_json() == second.get_json()
        mock_callbacks["start"].assert_called_once()

    def test_start_returns_conflict_for_same_key_and_other_payload(
        self, client: FlaskClient, mock_callbacks: dict[str, MagicMock]
    ) -> None:
        headers = {"Idempotency-Key": "same-start-key-002"}

        first = client.post(
            "/api/start",
            json={"area": "full", "fps": 30},
            content_type="application/json",
            headers=headers,
        )
        second = client.post(
            "/api/start",
            json={"area": "full", "fps": 60},
            content_type="application/json",
            headers=headers,
        )

        assert first.status_code == 200
        assert second.status_code == 409
        data = assert_error_contract(second, "idempotency_conflict")
        assert "другого запроса" in data["error"]["message"]
        mock_callbacks["start"].assert_called_once()


class TestAPIObservability:
    """Тесты request-id и расширенного health payload."""

    def test_request_id_is_preserved_on_api_response(
        self, client: FlaskClient
    ) -> None:
        """Проверка прокидывания X-Request-ID в ответ."""
        response = client.get(
            "/api/status", headers={"X-Request-ID": "request-abc-123"}
        )

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "request-abc-123"

    def test_request_id_is_generated_for_health(
        self, unauth_client: FlaskClient
    ) -> None:
        """Проверка генерации X-Request-ID при отсутствии заголовка."""
        response = unauth_client.get("/health")

        assert response.status_code == 200
        assert response.headers["X-Request-ID"]

    def test_health_includes_observability_fields(
        self, unauth_client: FlaskClient
    ) -> None:
        """Проверка расширенного payload health endpoint."""
        server = APIServer()
        response = unauth_client.get("/health")
        data = response.get_json()

        assert response.status_code == 200
        assert data["status"] == "ok"
        assert "timestamp" in data
        assert data["version"] == server._version
        assert data["version"] != "unknown"
        assert isinstance(data["uptime_seconds"], (int, float))
        assert data["uptime_seconds"] >= 0
        assert "websocket" in data
        assert data["websocket"]["transport_ready"] is True
        assert data["websocket"]["buffered_events"] >= 1
        assert data["websocket"]["events_published_total"] >= 1
        assert data["websocket"]["attached_to_event_bus"] is False
