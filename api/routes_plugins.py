"""
Доменные маршруты REST API для управления плагинами (Issue #124).
================================================================

Предоставляет эндпоинты:
- GET  /api/v1/plugins                — список всех обнаруженных плагинов;
- GET  /api/v1/plugins/<name>         — метаданные и JSON Schema плагина;
- POST /api/v1/plugins/<name>/enable  — включение плагина;
- POST /api/v1/plugins/<name>/disable — отключение плагина;
- PUT  /api/v1/plugins/<name>/config  — обновление конфигурации плагина.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify
from werkzeug.exceptions import BadRequest

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from logger_config import get_module_logger

logger = get_module_logger(__name__)


def register_plugins_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    parse_request_json: Any,
    handle_validation_error: Any,
    internal_error_response: Any,
    exception_response: Any,
    error_response: Any,
) -> None:
    """Регистрирует маршруты управления плагинами."""

    @api_v1.route("/plugins", methods=["GET"])
    @require_api_key
    def list_plugins() -> Any:
        """Получение списка всех зарегистрированных плагинов."""
        try:
            callback = server.get_callback("get_plugins")
            if callback:
                plugins = callback()
                return jsonify({"success": True, "data": plugins}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка получения списка плагинов: %s", e)
            return exception_response(e)

    @api_v1.route("/plugins/<name>", methods=["GET"])
    @require_api_key
    def get_plugin(name: str) -> Any:
        """Получение метаданных и схемы настроек конкретного плагина."""
        try:
            callback = server.get_callback("get_plugin_info")
            if callback:
                info = callback(name)
                if info is None:
                    return error_response(
                        404, "not_found", f"Плагин '{name}' не найден"
                    )
                return jsonify({"success": True, "data": info}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception(
                "Ошибка получения информации о плагине %s: %s", name, e
            )
            return exception_response(e)

    @api_v1.route("/plugins/<name>/enable", methods=["POST"])
    @rate_limit
    @require_api_key
    def enable_plugin(name: str) -> Any:
        """Включение плагина."""
        try:
            callback = server.get_callback("enable_plugin")
            if callback:
                success = callback(name)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось включить плагин '{name}'",
                    )
                return jsonify(
                    {"success": True, "message": f"Плагин '{name}' включён"}
                ), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка при включении плагина %s: %s", name, e)
            return exception_response(e)

    @api_v1.route("/plugins/<name>/disable", methods=["POST"])
    @rate_limit
    @require_api_key
    def disable_plugin(name: str) -> Any:
        """Отключение плагина."""
        try:
            callback = server.get_callback("disable_plugin")
            if callback:
                success = callback(name)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось отключить плагин '{name}'",
                    )
                return jsonify(
                    {"success": True, "message": f"Плагин '{name}' отключён"}
                ), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка при отключении плагина %s: %s", name, e)
            return exception_response(e)

    @api_v1.route("/plugins/<name>/config", methods=["PUT"])
    @rate_limit
    @require_api_key
    def configure_plugin(name: str) -> Any:
        """Обновление настроек плагина."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            if not isinstance(data, dict):
                return error_response(
                    400, "bad_request", "Ожидается JSON объект настроек"
                )

            callback = server.get_callback("configure_plugin")
            if callback:
                success = callback(name, data)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось обновить настройки плагина '{name}'",
                    )
                return jsonify(
                    {
                        "success": True,
                        "message": f"Настройки плагина '{name}' обновлены",
                    }
                ), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при настройке плагина %s: %s", name, e)
            return exception_response(e)
