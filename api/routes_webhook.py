"""Доменные маршруты API для настройки webhook-уведомлений (#52)."""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import ConfigureWebhookRequest


def register_webhook_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    parse_request_json: Any,
    handle_validation_error: Any,
    internal_error_response: Any,
    exception_response: Any,
) -> None:
    """Регистрирует маршруты настройки и проверки webhook."""

    @api_v1.route("config/webhook", methods=["GET"])
    @require_api_key
    def get_webhook_config() -> Any:
        """Получение настроек webhook (без значения секрета)."""
        try:
            callback = server.get_callback("get_webhook_config")
            if callback:
                return jsonify({"success": True, "data": callback()})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения настроек webhook: {e}")
            return exception_response(e)

    @api_v1.route("config/webhook", methods=["POST"])
    @rate_limit
    @require_api_key
    def configure_webhook() -> Any:
        """Настройка webhook-уведомлений (URL, секрет, включение)."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            try:
                validated = ConfigureWebhookRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback = server.get_callback("configure_webhook")
            if callback:
                result = callback(
                    validated.url, validated.secret, validated.enabled
                )
                return jsonify(
                    {"success": result.get("success", False), "data": result}
                )
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка настройки webhook: {e}")
            return exception_response(e)

    @api_v1.route("config/webhook/test", methods=["POST"])
    @rate_limit
    @require_api_key
    def test_webhook() -> Any:
        """Отправка тестового webhook-уведомления текущими настройками."""
        try:
            callback = server.get_callback("test_webhook")
            if callback:
                result = callback()
                return jsonify(
                    {"success": result.get("success", False), "data": result}
                )
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка тестовой отправки webhook: {e}")
            return exception_response(e)
