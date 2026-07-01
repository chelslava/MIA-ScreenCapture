"""Доменные маршруты API для сценариев записи."""

from __future__ import annotations

from typing import Any

from flask import jsonify, request
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import (
    FilePathRequest,
    StartRecordingRequest,
    SwitchCaptureSourceRequest,
)


def register_recording_routes(
    api_v1: Any,
    server: Any,
    *,
    logger: Any,
    parse_request_json: Any,
    handle_validation_error: Any,
    execute_with_idempotency: Any,
    stop_operation_response: Any,
    internal_error_response: Any,
    exception_response: Any,
    error_response: Any,
) -> tuple[Any, Any, Any]:
    """Регистрирует маршруты управления записью."""

    @api_v1.route("/start", methods=["POST"])
    @rate_limit
    @require_api_key
    def start_recording() -> Any:
        """Начало новой записи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = StartRecordingRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(exclude_none=True)

                callback = server.get_callback("start")
                if callback:
                    result = callback(callback_data)
                    if result.get("success"):
                        return jsonify({"success": True, "data": result})
                    return jsonify(
                        {
                            "success": False,
                            "error": result.get(
                                "error", "Не удалось начать запись"
                            ),
                        }
                    ), 400

                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка начала записи: {e}")
            return exception_response(e)

    @api_v1.route("stop", methods=["POST"])
    @rate_limit
    @require_api_key
    def stop_recording() -> Any:
        """Остановка текущей записи."""
        try:
            return execute_with_idempotency(
                server,
                lambda: stop_operation_response(server),
            )
        except Exception as e:
            logger.exception(f"Ошибка остановки записи: {e}")
            return exception_response(e)

    @api_v1.route("pause", methods=["POST"])
    @rate_limit
    @require_api_key
    def pause_recording() -> Any:
        """Пауза или возобновление текущей записи."""
        try:

            def _handler() -> Any:
                callback = server.get_callback("pause")
                if callback:
                    result = callback()
                    return jsonify({"success": True, "data": result})
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка паузы записи: {e}")
            return exception_response(e)

    @api_v1.route("recording/switch-source", methods=["POST"])
    @rate_limit
    @require_api_key
    def switch_capture_source() -> Any:
        """Переключение источника захвата активной записи (#48)."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = SwitchCaptureSourceRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback_data = validated.model_dump(exclude_none=True)

                callback = server.get_callback("switch_capture_source")
                if callback:
                    result = callback(callback_data)
                    if result.get("success"):
                        return jsonify({"success": True, "data": result})
                    return jsonify(
                        {
                            "success": False,
                            "error": result.get(
                                "error",
                                "Не удалось переключить источник захвата",
                            ),
                        }
                    ), 400

                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка переключения источника захвата: {e}")
            return exception_response(e)

    @api_v1.route("recordings", methods=["GET"])
    @require_api_key
    def get_recordings() -> Any:
        """Получение списка недавних записей."""
        try:
            callback = server.get_callback("recordings")
            if callback:
                recordings = callback()
                return jsonify({"success": True, "data": recordings})
            return internal_error_response()

        except Exception as e:
            logger.exception(f"Ошибка получения записей: {e}")
            return exception_response(e)

    @api_v1.route("recordings/verify", methods=["POST"])
    @rate_limit
    @require_api_key
    def verify_recording() -> Any:
        """Проверка целостности видеофайла по указанному пути (#46)."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            try:
                validated = FilePathRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback = server.get_callback("verify_recording")
            if callback:
                result = callback(validated.file_path)
                return jsonify({"success": True, "data": result})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка проверки целостности файла: {e}")
            return exception_response(e)

    @api_v1.route("recordings/repair", methods=["POST"])
    @rate_limit
    @require_api_key
    def repair_recording() -> Any:
        """Попытка восстановления видеофайла по указанному пути (#46)."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            try:
                validated = FilePathRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback = server.get_callback("repair_recording")
            if callback:
                result = callback(validated.file_path)
                return jsonify({"success": True, "data": result})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка восстановления файла: {e}")
            return exception_response(e)

    @api_v1.route("events/recent", methods=["GET"])
    @require_api_key
    def get_recent_events() -> Any:
        """Получение недавних real-time событий записи."""
        try:
            limit_raw = request.args.get("limit", "50")
            try:
                limit = int(limit_raw)
            except ValueError:
                return error_response(
                    400,
                    "validation_error",
                    "Параметр limit должен быть числом",
                )

            manager = server.get_websocket_manager()
            if manager is None:
                return jsonify({"success": True, "data": []})

            events = manager.get_recent_events(limit=limit)
            return jsonify({"success": True, "data": events})
        except Exception as e:
            logger.exception(f"Ошибка получения событий: {e}")
            return exception_response(e)

    @api_v1.route("events/stats", methods=["GET"])
    @require_api_key
    def get_events_stats() -> Any:
        """Получение статистики real-time event-менеджера."""
        try:
            manager = server.get_websocket_manager()
            if manager is None:
                return jsonify(
                    {
                        "success": True,
                        "data": {"transport_ready": False},
                    }
                )
            return jsonify({"success": True, "data": manager.get_stats()})
        except Exception as e:
            logger.exception(f"Ошибка получения статистики событий: {e}")
            return exception_response(e)

    return start_recording, stop_recording, pause_recording
