"""Доменные маршруты API для ресурсов окружения и observability."""

from __future__ import annotations

from typing import Any

from flask import jsonify

from api.auth import require_api_key


def register_resource_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    internal_error_response: Any,
    exception_response: Any,
) -> None:
    """Регистрирует маршруты ресурсов окружения."""

    @api_v1.route("devices", methods=["GET"])
    @require_api_key
    def get_devices() -> Any:
        """Получение доступных аудиоустройств."""
        try:
            callback = server.get_callback("devices")
            if callback:
                devices = callback()
                return jsonify({"success": True, "data": devices})
            return internal_error_response()

        except Exception as e:
            logger.exception(f"Ошибка получения устройств: {e}")
            return exception_response(e)

    @api_v1.route("windows", methods=["GET"])
    @require_api_key
    def get_windows() -> Any:
        """Получение доступных окон для захвата."""
        try:
            callback = server.get_callback("windows")
            if callback:
                windows = callback()
                return jsonify({"success": True, "data": windows})
            return internal_error_response()

        except Exception as e:
            logger.exception(f"Ошибка получения окон: {e}")
            return exception_response(e)


def register_observability_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    exception_response: Any,
) -> None:
    """Регистрирует маршруты observability."""

    @api_v1.route("observability/metrics", methods=["GET"])
    @require_api_key
    def get_observability_metrics() -> Any:
        """Получение эксплуатационных метрик API."""
        try:
            return jsonify(
                {
                    "success": True,
                    "data": server.get_observability_metrics(),
                }
            )
        except Exception as e:
            logger.exception(f"Ошибка получения observability metrics: {e}")
            return exception_response(e)

    @api_v1.route("observability/baseline", methods=["GET"])
    @require_api_key
    def get_observability_baseline() -> Any:
        """Получение baseline SLO по эксплуатационным метрикам."""
        try:
            return jsonify(
                {
                    "success": True,
                    "data": server.get_observability_baseline(),
                }
            )
        except Exception as e:
            logger.exception(f"Ошибка получения observability baseline: {e}")
            return exception_response(e)
