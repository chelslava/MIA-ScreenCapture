"""Доменные маршруты API для конфигурации."""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import UpdateConfigRequest


def register_config_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    parse_request_json: Any,
    handle_validation_error: Any,
    execute_with_idempotency: Any,
    internal_error_response: Any,
    exception_response: Any,
) -> None:
    """Регистрирует маршруты конфигурации."""

    @api_v1.route("config", methods=["GET"])
    @require_api_key
    def get_config() -> Any:
        """Получение текущей конфигурации."""
        try:
            callback = server.get_callback("get_config")
            if callback:
                config = callback()
                return jsonify({"success": True, "data": config})
            return internal_error_response()

        except Exception as e:
            logger.exception(f"Ошибка получения конфигурации: {e}")
            return exception_response(e)

    @api_v1.route("config", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_config() -> Any:
        """Обновление конфигурации."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = UpdateConfigRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(
                    exclude_none=True,
                    exclude={"video", "audio", "output", "app"},
                )

                callback = server.get_callback("update_config")
                if callback:
                    result = callback(callback_data)
                    return jsonify({"success": True, "data": result})
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка обновления конфигурации: {e}")
            return exception_response(e)
