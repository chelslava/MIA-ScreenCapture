"""Доменные маршруты API для планировщика."""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import (
    CreateScheduleRequest,
    ToggleScheduleRequest,
    UpdateScheduleRequest,
)


def register_schedule_routes(
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
    """Регистрирует маршруты планировщика."""

    @api_v1.route("schedule", methods=["GET"])
    @require_api_key
    def get_schedule() -> Any:
        """Получение списка запланированных задач."""
        try:
            callback = server.get_callback("get_schedule")
            if callback:
                tasks = callback()
                return jsonify({"success": True, "data": tasks})
            return internal_error_response()

        except Exception as e:
            logger.exception(f"Ошибка получения расписания: {e}")
            return exception_response(e)

    @api_v1.route("schedule", methods=["POST"])
    @rate_limit
    @require_api_key
    def create_schedule() -> Any:
        """Создание новой запланированной задачи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = CreateScheduleRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(exclude_none=True)

                if validated.params:
                    callback_data["params"] = validated.params.model_dump(
                        exclude_none=True
                    )

                callback = server.get_callback("create_schedule")
                if callback:
                    result = callback(callback_data)
                    if result.get("success"):
                        return jsonify({"success": True, "data": result})
                    return jsonify(
                        {
                            "success": False,
                            "error": result.get(
                                "error", "Не удалось создать задачу"
                            ),
                        }
                    ), 400

                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка создания расписания: {e}")
            return exception_response(e)

    @api_v1.route("schedule/<task_id>", methods=["DELETE"])
    @rate_limit
    @require_api_key
    def delete_schedule(task_id: str) -> Any:
        """Удаление запланированной задачи."""
        try:

            def _handler() -> Any:
                callback = server.get_callback("delete_schedule")
                if callback:
                    result = callback(task_id)
                    return jsonify(
                        {
                            "success": result.get("success", True),
                            "data": result,
                        }
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка удаления расписания: {e}")
            return exception_response(e)

    @api_v1.route("schedule/<task_id>", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_schedule(task_id: str) -> Any:
        """Обновление запланированной задачи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None
                data["id"] = task_id

                try:
                    validated = UpdateScheduleRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(exclude_none=True)

                callback = server.get_callback("update_schedule")
                if callback:
                    result = callback(callback_data)
                    return jsonify(
                        {
                            "success": result.get("success", True),
                            "data": result,
                        }
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка обновления расписания: {e}")
            return exception_response(e)

    @api_v1.route("schedule/<task_id>/toggle", methods=["POST"])
    @rate_limit
    @require_api_key
    def toggle_schedule(task_id: str) -> Any:
        """Включение или отключение запланированной задачи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = ToggleScheduleRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback = server.get_callback("toggle_schedule")
                if callback:
                    result = callback(task_id, validated.enabled)
                    return jsonify({"success": True, "data": result})
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка переключения расписания: {e}")
            return exception_response(e)
