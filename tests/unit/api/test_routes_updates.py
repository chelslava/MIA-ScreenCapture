"""
Unit-тесты REST API маршрутов авто-обновления (api/routes_updates.py).
====================================================================
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask

from api.routes_updates import create_updates_blueprint


@pytest.fixture
def mock_server() -> MagicMock:
    server = MagicMock()
    server.is_idempotency_enabled.return_value = False
    return server


@pytest.fixture
def client(mock_server: MagicMock):
    app = Flask(__name__)
    app.config["TESTING"] = True
    bp = create_updates_blueprint(mock_server)
    app.register_blueprint(bp)
    return app.test_client()


class TestRoutesUpdates:
    """Тесты REST API для авто-обновления."""

    def test_get_update_config(self, client, mock_server: MagicMock) -> None:
        mock_server.get_callback.return_value = lambda: {
            "check_on_startup": True,
            "auto_download": False,
            "channel": "stable",
            "check_interval_hours": 24,
        }
        res = client.get("/api/v1/updates/config")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["channel"] == "stable"

    def test_update_update_config(
        self, client, mock_server: MagicMock
    ) -> None:
        mock_server.get_callback.return_value = lambda data: {
            "success": True,
            "config": {
                "check_on_startup": False,
                "auto_download": True,
                "channel": "beta",
                "check_interval_hours": 12,
            },
        }
        payload = {
            "check_on_startup": False,
            "auto_download": True,
            "channel": "beta",
            "check_interval_hours": 12,
        }
        res = client.put("/api/v1/updates/config", json=payload)
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["channel"] == "beta"

    def test_check_for_updates_endpoint(
        self, client, mock_server: MagicMock
    ) -> None:
        mock_server.get_callback.return_value = lambda force=False: {
            "update_available": True,
            "current_version": "1.0.0",
            "latest_release": {"version": "2.0.0"},
        }
        res = client.get("/api/v1/updates/check?force=true")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["update_available"] is True

    def test_download_update_endpoint(
        self, client, mock_server: MagicMock
    ) -> None:
        mock_server.get_callback.return_value = lambda version=None: {
            "success": True,
            "message": "Downloading",
        }
        res = client.post(
            "/api/v1/updates/download", json={"version": "2.0.0"}
        )
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_apply_update_endpoint(
        self, client, mock_server: MagicMock
    ) -> None:
        mock_server.get_callback.return_value = lambda: {
            "success": True,
            "message": "Applied",
        }
        res = client.post("/api/v1/updates/apply")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True

    def test_get_update_status(self, client, mock_server: MagicMock) -> None:
        mock_server.get_callback.return_value = lambda: {
            "status": "idle",
            "current_version": "1.0.0",
        }
        res = client.get("/api/v1/updates/status")
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["data"]["status"] == "idle"
