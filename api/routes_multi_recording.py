"""Маршруты API для мультиисточниковой записи (#51)."""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import StartMultiRecordingRequest


def register_multi_recording_routes(
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
    """Регистрирует маршруты мультиисточниковой записи."""

    @api_v1.route("recording/start-multi", methods=["POST"])
    @rate_limit
    @require_api_key
    def start_multi_recording() -> Any:
        """Начало записи с нескольких источников одновременно (#51)."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = StartMultiRecordingRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(exclude_none=True)

                callback = server.get_callback("start_multi_recording")
                if callback:
                    result = callback(callback_data)
                    if result.get("success"):
                        return jsonify({"success": True, "data": result})
                    return jsonify(
                        {
                            "success": False,
                            "error": result.get(
                                "error",
                                "Не удалось начать мультиисточниковую запись",
                            ),
                        }
                    ), 400

                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка начала мультиисточниковой записи: {e}")
            return exception_response(e)

    @api_v1.route("recording/stop-multi", methods=["POST"])
    @rate_limit
    @require_api_key
    def stop_multi_recording() -> Any:
        """Остановка мультиисточниковой записи (#51)."""
        try:

            def _handler() -> Any:
                callback = server.get_callback("stop_multi_recording")
                if callback:
                    result = callback()
                    if result.get("success"):
                        return jsonify({"success": True, "data": result})
                    return jsonify(
                        {
                            "success": False,
                            "error": result.get(
                                "error",
                                "Не удалось остановить мультиисточниковую "
                                "запись",
                            ),
                        }
                    ), 400
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(
                f"Ошибка остановки мультиисточниковой записи: {e}"
            )
            return exception_response(e)

    @api_v1.route("recording/status-multi", methods=["GET"])
    @require_api_key
    def get_multi_recording_status() -> Any:
        """Статус мультиисточниковой записи (#51)."""
        try:
            callback = server.get_callback("get_multi_recording_status")
            if callback:
                status = callback()
                return jsonify({"success": True, "data": status})
            return internal_error_response()
        except Exception as e:
            logger.exception(
                f"Ошибка получения статуса мультиисточниковой записи: {e}"
            )
            return exception_response(e)
