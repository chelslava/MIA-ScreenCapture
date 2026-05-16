"""Интеграционные snapshot/contract тесты ключевых API-ответов."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from flask.testing import FlaskClient

from api.auth import init_api_auth
from api.routes import register_routes
from api.server import APIServer
from api.websocket import WebSocketManager

TEST_API_KEY = "test-api-key-contract-snapshots-12345"


def _assert_exact_keys(
    payload: dict[str, Any],
    expected_keys: set[str],
) -> None:
    """Проверяет точный набор ключей в payload."""
    assert set(payload.keys()) == expected_keys


@pytest.fixture
def api_server() -> Generator[APIServer, None, None]:
    """Создаёт API сервер с детерминированными callbacks."""
    server = APIServer(host="127.0.0.1", port=5013)
    init_api_auth(server.app, api_key=TEST_API_KEY)

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
    server.set_callback(
        "get_config",
        MagicMock(
            return_value={
                "video": {"fps": 30, "codec": "libx264"},
                "audio": {"sample_rate": 44100},
            }
        ),
    )

    websocket_manager = WebSocketManager()
    websocket_manager.publish(
        {
            "type": "started",
            "timestamp": "2026-03-23T12:00:00+00:00",
            "data": {"output_path": "C:\\videos\\contract.mp4"},
        }
    )
    server.set_websocket_manager(websocket_manager)
    server._check_ffmpeg = lambda: {"status": "ok"}
    server._check_disk = lambda: {"status": "ok", "free_gb": 100.0}

    register_routes(server.app, server)
    server.app.config["TESTING"] = True
    yield server
    server.stop()


@pytest.fixture
def auth_client(api_server: APIServer) -> FlaskClient:
    """Создаёт авторизованный Flask client."""
    client = api_server.app.test_client()
    client.environ_base["HTTP_X_API_KEY"] = TEST_API_KEY
    return client


@pytest.fixture
def unauth_client(api_server: APIServer) -> FlaskClient:
    """Создаёт неавторизованный Flask client."""
    return api_server.app.test_client()


class TestAPIContractSnapshots:
    """Проверяет контракт ответов ключевых API endpoint-ов."""

    def test_health_response_contract_snapshot(
        self,
        unauth_client: FlaskClient,
    ) -> None:
        """Проверяет стабильный контракт `/health`."""
        response = unauth_client.get(
            "/health",
            headers={"X-Request-ID": "contract-health-001"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == "contract-health-001"

        payload = response.get_json()
        _assert_exact_keys(
            payload,
            {
                "status",
                "timestamp",
                "uptime_seconds",
                "version",
                "websocket",
                "checks",
            },
        )
        assert payload["status"] == "ok"
        assert isinstance(payload["timestamp"], str)
        assert isinstance(payload["uptime_seconds"], int | float)
        assert isinstance(payload["version"], str)

        websocket = payload["websocket"]
        _assert_exact_keys(
            websocket,
            {
                "transport_ready",
                "buffered_events",
                "events_published_total",
                "attached_to_event_bus",
            },
        )
        assert isinstance(websocket["transport_ready"], bool)
        assert isinstance(websocket["buffered_events"], int)
        assert isinstance(websocket["events_published_total"], int)
        assert isinstance(websocket["attached_to_event_bus"], bool)

    def test_status_response_contract_snapshot(
        self,
        auth_client: FlaskClient,
    ) -> None:
        """Проверяет стабильный контракт `/api/v1/status`."""
        response = auth_client.get(
            "/api/v1/status",
            headers={"X-Request-ID": "contract-status-001"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == "contract-status-001"

        payload = response.get_json()
        _assert_exact_keys(payload, {"success", "data"})
        assert payload["success"] is True
        assert payload["data"] == {
            "is_recording": False,
            "is_paused": False,
            "elapsed_time": 0,
            "current_file": None,
        }

    def test_config_response_contract_snapshot(
        self,
        auth_client: FlaskClient,
    ) -> None:
        """Проверяет стабильный контракт `/api/v1/config`."""
        response = auth_client.get(
            "/api/v1/config",
            headers={"X-Request-ID": "contract-config-001"},
        )

        assert response.status_code == 200
        assert response.headers.get("X-Request-ID") == "contract-config-001"

        payload = response.get_json()
        _assert_exact_keys(payload, {"success", "data"})
        assert payload["success"] is True
        assert payload["data"] == {
            "video": {"fps": 30, "codec": "libx264"},
            "audio": {"sample_rate": 44100},
        }
