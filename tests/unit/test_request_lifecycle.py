"""Юнит-тесты request lifecycle middleware API."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from flask import Flask, jsonify

from api.request_lifecycle import register_request_lifecycle


@dataclass
class _DummyObservability:
    """Тестовый сборщик вызовов observability middleware."""

    started_count: int = 0
    finished_calls: list[dict[str, Any]] = field(default_factory=list)

    def request_started(self) -> None:
        self.started_count += 1

    def request_finished(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        latency_seconds: float,
    ) -> None:
        self.finished_calls.append(
            {
                "method": method,
                "path": path,
                "status_code": status_code,
                "latency_seconds": latency_seconds,
            }
        )


def _create_app_with_middleware() -> tuple[Flask, _DummyObservability]:
    app = Flask(__name__)
    obs = _DummyObservability()

    register_request_lifecycle(
        app,
        request_id_header="X-Request-ID",
        observability=obs,
        health_payload_factory=lambda: {"status": "ok"},
        access_log_level_resolver=lambda _path, _status: logging.INFO,
    )

    @app.route("/ping", methods=["GET"])
    def ping() -> Any:
        return jsonify({"ok": True})

    app.config["TESTING"] = True
    return app, obs


def test_health_request_tracked_by_observability() -> None:
    """Проверяет что /health запрос отслеживается observability и заголовок request id выставляется."""
    app, obs = _create_app_with_middleware()

    @app.route("/health", methods=["GET"])
    def health() -> Any:
        return jsonify({"status": "ok"})

    client = app.test_client()

    response = client.get("/health", headers={"X-Request-ID": "req-health-1"})

    assert response.status_code == 200
    assert response.get_json()["status"] == "ok"
    assert response.headers["X-Request-ID"] == "req-health-1"
    assert obs.started_count == 1
    assert len(obs.finished_calls) == 1
    assert obs.finished_calls[0]["path"] == "/health"
    assert obs.finished_calls[0]["status_code"] == 200


def test_regular_request_updates_observability() -> None:
    """Проверяет middleware поведение для обычного endpoint."""
    app, obs = _create_app_with_middleware()
    client = app.test_client()

    response = client.get("/ping", headers={"X-Request-ID": "req-ping-1"})

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert response.headers["X-Request-ID"] == "req-ping-1"
    assert obs.started_count == 1
    assert len(obs.finished_calls) == 1
    assert obs.finished_calls[0]["method"] == "GET"
    assert obs.finished_calls[0]["path"] == "/ping"
    assert obs.finished_calls[0]["status_code"] == 200
    assert obs.finished_calls[0]["latency_seconds"] >= 0.0
