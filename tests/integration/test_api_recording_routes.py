"""Интеграционные тесты маршрутов записи API.

Покрывает happy-path и негативные сценарии для `/api/start`,
`/api/stop` и `/api/pause`.
"""

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from api.auth import init_api_auth
from api.routes import register_routes
from api.runtime_models import APIOperation, IdempotencyBeginResult
from api.server import APIServer

TEST_API_KEY = "test-api-key-for-recording-routes-12345"
TEST_REQUEST_ID = "req-recording-routes"
STOP_OPERATION_ID = "stop-operation-001"
STOP_OPERATION_WAIT_SECONDS = 0.2


def _make_headers(
    request_id: str,
    api_key: str | None = TEST_API_KEY,
) -> dict[str, str]:
    """Собирает заголовки запроса для тестов API."""
    headers = {"X-Request-ID": request_id}
    if api_key is not None:
        headers["X-API-Key"] = api_key
    return headers


def assert_error_contract(
    response: Any,
    expected_code: str,
    request_id: str,
) -> dict[str, Any]:
    """Проверяет единый контракт ошибки API."""
    data = response.get_json()

    assert response.headers.get("X-Request-ID") == request_id
    assert data["success"] is False
    assert data["trace_id"] == request_id

    error = data["error"]
    assert error["code"] == expected_code
    assert isinstance(error["message"], str)
    assert "details" in error
    return data


def _build_callbacks() -> dict[str, MagicMock]:
    """Создаёт стабилизированные callbacks для маршрутов записи."""
    return {
        "start": MagicMock(
            return_value={
                "success": True,
                "output_path": "C:\\videos\\recording.mp4",
            }
        ),
        "stop": MagicMock(
            return_value={
                "success": True,
                "output_path": "C:\\videos\\recording.mp4",
                "duration": 12.5,
            }
        ),
        "pause": MagicMock(return_value={"success": True, "is_paused": True}),
    }


def _install_stop_operation_stubs(
    server: APIServer,
) -> None:
    """Подменяет фоновые операции остановки на синхронный сценарий."""
    operation_state: dict[str, dict[str, Any] | None] = {"operation": None}

    def submit_background_operation(
        operation_type: str,
        runner: Callable[[], Any],
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> APIOperation:
        result = runner()
        operation = {
            "id": STOP_OPERATION_ID,
            "type": operation_type,
            "status": "succeeded",
            "result": result,
            "error": None,
            "request_id": request_id,
            "trace_id": trace_id,
            "client_ip": client_ip,
        }
        operation_state["operation"] = operation
        return APIOperation.from_dict(operation)

    def wait_for_background_operation(
        operation_id: str,
        timeout: float,
    ) -> APIOperation | None:
        assert timeout == STOP_OPERATION_WAIT_SECONDS
        operation = operation_state["operation"]
        if operation is None:
            return None
        if operation["id"] != operation_id:
            return None
        return APIOperation.from_dict(operation)

    server.submit_background_operation = MagicMock(
        side_effect=submit_background_operation
    )
    server.wait_for_background_operation = MagicMock(
        side_effect=wait_for_background_operation
    )


def _create_server(
    *,
    include_stop_callback: bool = True,
) -> tuple[APIServer, dict[str, MagicMock]]:
    """Создаёт тестовый API сервер с детерминированными callback'ами."""
    callbacks = _build_callbacks()
    server = APIServer(host="127.0.0.1", port=5011)

    init_api_auth(server.app, api_key=TEST_API_KEY)
    server.set_callback("start", callbacks["start"])
    if include_stop_callback:
        server.set_callback("stop", callbacks["stop"])
    server.set_callback("pause", callbacks["pause"])

    if include_stop_callback:
        _install_stop_operation_stubs(server)

    register_routes(server.app, server)

    # Мокируем проверки компонентов для стабильного поведения в CI
    server._check_ffmpeg = lambda: {"status": "ok"}
    server._check_disk = lambda: {"status": "ok", "free_gb": 100.0}

    server.app.config["TESTING"] = True
    return server, callbacks


@pytest.fixture
def recording_setup() -> tuple[APIServer, dict[str, MagicMock]]:
    """Сервер и callback'и для успешных сценариев записи."""
    return _create_server()


@pytest.fixture
def recording_server(
    recording_setup: tuple[APIServer, dict[str, MagicMock]],
) -> APIServer:
    """API сервер для маршрутов записи."""
    return recording_setup[0]


@pytest.fixture
def recording_callbacks(
    recording_setup: tuple[APIServer, dict[str, MagicMock]],
) -> dict[str, MagicMock]:
    """Callback'и, привязанные к тестовому API серверу."""
    return recording_setup[1]


@pytest.fixture
def recording_client(recording_server: APIServer) -> FlaskClient:
    """Авторизованный клиент для маршрутов записи."""
    client = recording_server.app.test_client()
    client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


@pytest.fixture
def recording_server_without_stop() -> APIServer:
    """Сервер без callback'а остановки для проверки ошибки конфигурации."""
    server, _ = _create_server(include_stop_callback=False)
    return server


@pytest.fixture
def recording_client_without_stop(
    recording_server_without_stop: APIServer,
) -> FlaskClient:
    """Авторизованный клиент без callback'а stop."""
    client = recording_server_without_stop.app.test_client()
    client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


class TestRecordingRoutesAuth:
    """Тесты прав доступа к маршрутам записи."""

    @pytest.mark.parametrize(
        ("path", "request_id"),
        [
            ("/api/start", "req-start-auth"),
            ("/api/stop", "req-stop-auth"),
            ("/api/pause", "req-pause-auth"),
        ],
    )
    def test_routes_require_api_key(
        self,
        recording_server: APIServer,
        path: str,
        request_id: str,
    ) -> None:
        """Проверяет, что все маршруты записи требуют API ключ."""
        client = recording_server.app.test_client()
        response = client.post(path, headers=_make_headers(request_id, None))

        assert response.status_code == 401
        assert_error_contract(response, "unauthorized", request_id)

    def test_route_rejects_invalid_api_key(
        self,
        recording_server: APIServer,
    ) -> None:
        """Проверяет отклонение неверного API ключа."""
        request_id = "req-start-invalid-key"
        client = recording_server.app.test_client()
        response = client.post(
            "/api/start",
            headers=_make_headers(request_id, api_key="invalid-key"),
        )

        assert response.status_code == 401
        assert_error_contract(response, "unauthorized", request_id)


class TestStartRecordingRoute:
    """Тесты маршрута `/api/start`."""

    def test_start_recording_happy_path(
        self,
        recording_client: FlaskClient,
        recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверяет успешный запуск записи."""
        request_id = f"{TEST_REQUEST_ID}-start-ok"
        request_data = {
            "area": "rect",
            "rect": [10, 10, 1280, 720],
            "audio": "mic",
            "fps": 60,
            "codec": "libx265",
            "bitrate": "5M",
            "duration": 12,
        }

        response = recording_client.post(
            "/api/start",
            json=request_data,
            headers=_make_headers(request_id),
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == request_id

        data = response.get_json()
        assert data["success"] is True
        assert data["data"] == {
            "success": True,
            "output_path": "C:\\videos\\recording.mp4",
        }

        recording_callbacks["start"].assert_called_once_with(request_data)

    def test_start_recording_validation_error(
        self,
        recording_client: FlaskClient,
    ) -> None:
        """Проверяет контракт ошибки валидации для `/api/start`."""
        request_id = f"{TEST_REQUEST_ID}-start-validation"
        response = recording_client.post(
            "/api/start",
            json={"fps": 0},
            headers=_make_headers(request_id),
        )

        assert response.status_code == 400
        data = assert_error_contract(response, "validation_error", request_id)
        assert isinstance(data["error"]["details"], list)
        assert any(
            item.get("field") == "fps" for item in data["error"]["details"]
        )

    def test_start_recording_bad_json_contract(
        self,
        recording_client: FlaskClient,
    ) -> None:
        """Проверяет контракт ошибки для некорректного JSON."""
        request_id = f"{TEST_REQUEST_ID}-start-bad-json"
        response = recording_client.post(
            "/api/start",
            data="{bad-json",
            content_type="application/json",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 400
        assert_error_contract(response, "bad_request", request_id)


class TestStopRecordingRoute:
    """Тесты маршрута `/api/stop`."""

    def test_stop_recording_happy_path(
        self,
        recording_client: FlaskClient,
        recording_server: APIServer,
        recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверяет успешную остановку записи."""
        request_id = f"{TEST_REQUEST_ID}-stop-ok"
        response = recording_client.post(
            "/api/stop",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == request_id

        data = response.get_json()
        assert data["success"] is True
        assert data["data"]["success"] is True
        assert data["data"]["operation_id"] == STOP_OPERATION_ID
        assert data["data"]["status"] == "succeeded"
        assert data["data"]["output_path"] == "C:\\videos\\recording.mp4"
        assert data["data"]["duration"] == 12.5
        assert data["data"]["request_id"] == request_id
        assert data["data"]["trace_id"] == request_id
        assert data["data"]["client_ip"] == "127.0.0.1"

        recording_callbacks["stop"].assert_called_once_with()
        recording_server.submit_background_operation.assert_called_once()
        recording_server.wait_for_background_operation.assert_called_once_with(
            STOP_OPERATION_ID,
            STOP_OPERATION_WAIT_SECONDS,
        )

    def test_stop_recording_missing_callback_contract(
        self,
        recording_client_without_stop: FlaskClient,
    ) -> None:
        """Проверяет контракт ошибки при отсутствии callback'а stop."""
        request_id = f"{TEST_REQUEST_ID}-stop-missing-callback"
        response = recording_client_without_stop.post(
            "/api/stop",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 500
        assert_error_contract(response, "internal_error", request_id)

    def test_stop_recording_v1_returns_202_when_operation_running(
        self,
        recording_client: FlaskClient,
        recording_server: APIServer,
    ) -> None:
        """Проверяет контракт 202 для `/api/v1/stop` при running-операции."""
        request_id = f"{TEST_REQUEST_ID}-stop-v1-running"

        running_operation = APIOperation.from_dict(
            {
                "id": STOP_OPERATION_ID,
                "type": "stop",
                "status": "running",
                "created_at": "2026-03-30T10:00:00+00:00",
                "updated_at": "2026-03-30T10:00:00+00:00",
                "completed_at": None,
                "request_id": request_id,
                "trace_id": request_id,
                "client_ip": "127.0.0.1",
            }
        )
        recording_server.submit_background_operation = MagicMock(
            return_value=running_operation
        )
        recording_server.wait_for_background_operation = MagicMock(
            return_value=running_operation
        )

        response = recording_client.post(
            "/api/v1/stop",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 202
        assert response.headers.get("X-Request-ID") == request_id
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["operation_id"] == STOP_OPERATION_ID
        assert payload["data"]["type"] == "stop"
        assert payload["data"]["status"] == "running"
        assert payload["data"]["request_id"] == request_id
        assert payload["data"]["trace_id"] == request_id
        assert payload["data"]["client_ip"] == "127.0.0.1"

    def test_get_operation_status_v1_success(
        self,
        recording_client: FlaskClient,
        recording_server: APIServer,
    ) -> None:
        """Проверяет успешный контракт `/api/v1/operations/{id}`."""
        request_id = f"{TEST_REQUEST_ID}-operation-v1-ok"
        operation = APIOperation.from_dict(
            {
                "id": STOP_OPERATION_ID,
                "type": "stop",
                "status": "succeeded",
                "created_at": "2026-03-30T10:00:00+00:00",
                "updated_at": "2026-03-30T10:00:01+00:00",
                "completed_at": "2026-03-30T10:00:01+00:00",
                "result": {"success": True},
                "error": None,
                "request_id": request_id,
                "trace_id": request_id,
                "client_ip": "127.0.0.1",
            }
        )
        recording_server.get_background_operation = MagicMock(
            return_value=operation
        )

        response = recording_client.get(
            f"/api/v1/operations/{STOP_OPERATION_ID}",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == request_id
        payload = response.get_json()
        assert payload["success"] is True
        assert payload["data"]["operation_id"] == STOP_OPERATION_ID
        assert payload["data"]["status"] == "succeeded"
        assert payload["data"]["request_id"] == request_id
        assert payload["data"]["trace_id"] == request_id

    def test_get_operation_status_v1_not_found_contract(
        self,
        recording_client: FlaskClient,
        recording_server: APIServer,
    ) -> None:
        """Проверяет контракт 404 для `/api/v1/operations/{id}`."""
        request_id = f"{TEST_REQUEST_ID}-operation-v1-not-found"
        recording_server.get_background_operation = MagicMock(
            return_value=None
        )

        response = recording_client.get(
            "/api/v1/operations/nonexistent-operation",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 404
        assert_error_contract(response, "not_found", request_id)


class TestPauseRecordingRoute:
    """Тесты маршрута `/api/pause`."""

    def test_pause_recording_happy_path(
        self,
        recording_client: FlaskClient,
        recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверяет успешную постановку записи на паузу."""
        request_id = f"{TEST_REQUEST_ID}-pause-ok"
        response = recording_client.post(
            "/api/pause",
            headers=_make_headers(request_id),
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == request_id

        data = response.get_json()
        assert data["success"] is True
        assert data["data"] == {"success": True, "is_paused": True}

        recording_callbacks["pause"].assert_called_once_with()


class TestV1IdempotencyContracts:
    """Тесты v1 контрактов идемпотентности для write-endpoints."""

    def test_start_v1_returns_conflict_for_in_progress_idempotency(
        self,
        recording_client: FlaskClient,
        recording_server: APIServer,
        recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверяет `idempotency_in_progress` для `/api/v1/start`."""
        request_id = f"{TEST_REQUEST_ID}-idempotency-in-progress"
        recording_server.begin_idempotency_request = MagicMock(
            return_value=IdempotencyBeginResult.from_dict(
                {"state": "in_progress"}
            )
        )

        response = recording_client.post(
            "/api/v1/start",
            json={"area": "full", "fps": 30},
            headers={
                **_make_headers(request_id),
                "Idempotency-Key": "in-progress-key-001",
            },
        )

        assert response.status_code == 409
        assert_error_contract(response, "idempotency_in_progress", request_id)
        recording_callbacks["start"].assert_not_called()

    def test_start_v1_rejects_too_long_idempotency_key(
        self,
        recording_client: FlaskClient,
        recording_callbacks: dict[str, MagicMock],
    ) -> None:
        """Проверяет валидацию длины `Idempotency-Key` для `/api/v1/start`."""
        request_id = f"{TEST_REQUEST_ID}-idempotency-key-too-long"
        too_long_key = "k" * 129

        response = recording_client.post(
            "/api/v1/start",
            json={"area": "full", "fps": 30},
            headers={
                **_make_headers(request_id),
                "Idempotency-Key": too_long_key,
            },
        )

        assert response.status_code == 400
        data = assert_error_contract(response, "validation_error", request_id)
        assert "Idempotency-Key" in data["error"]["message"]
        recording_callbacks["start"].assert_not_called()
