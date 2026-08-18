"""
Доменные маршруты API для постобработки записей (Issue #118).
=============================================================

Предоставляет эндпоинты:
- GET  /api/v1/post-processing/config — получение настроек конвейера;
- PUT  /api/v1/post-processing/config — обновление настроек конвейера;
- GET  /api/v1/post-processing/status — статус текущей/последней постобработки;
- POST /api/v1/post-processing/run    — запуск конвейера для указанного файла;
- GET  /api/v1/recording/<id>/post-processing — статус постобработки записи.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import (
    RunPostProcessingRequest,
    UpdatePostProcessingConfigRequest,
)


def register_post_processing_routes(
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
    """Регистрирует маршруты управления постобработкой записей."""

    @api_v1.route("/post-processing/config", methods=["GET"])
    @require_api_key
    def get_post_processing_config() -> Any:
        """Получение текущих настроек постобработки."""
        try:
            callback = server.get_callback("get_post_processing_config")
            if callback:
                cfg = callback()
                return jsonify({"success": True, "data": cfg})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения настроек постобработки: {e}")
            return exception_response(e)

    @api_v1.route("/post-processing/config", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_post_processing_config() -> Any:
        """Обновление настроек постобработки."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = UpdatePostProcessingConfigRequest(**data)
                except ValidationError as ve:
                    return handle_validation_error(ve)

                callback = server.get_callback("update_post_processing_config")
                if callback:
                    clean_data = {
                        k: v
                        for k, v in validated.model_dump(
                            exclude_unset=True
                        ).items()
                        if v is not None
                    }
                    result = callback(clean_data)
                    if not result.get("success", False):
                        return jsonify(result), 400
                    return jsonify(result)
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка обновления настроек постобработки: {e}")
            return exception_response(e)

    @api_v1.route("/post-processing/status", methods=["GET"])
    @require_api_key
    def get_post_processing_status() -> Any:
        """Получение текущего статуса постобработки."""
        try:
            callback = server.get_callback("get_post_processing_status")
            if callback:
                status = callback()
                return jsonify({"success": True, "data": status})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения статуса постобработки: {e}")
            return exception_response(e)

    @api_v1.route("/post-processing/run", methods=["POST"])
    @rate_limit
    @require_api_key
    def run_post_processing() -> Any:
        """Ручной запуск постобработки для файла."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = RunPostProcessingRequest(**data)
                except ValidationError as ve:
                    return handle_validation_error(ve)

                callback = server.get_callback("run_post_processing")
                if callback:
                    result = callback(
                        file_path=validated.file_path,
                        params=validated.params,
                    )
                    if not result.get("success", False):
                        return jsonify(result), 400
                    return jsonify(result)
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка запуска постобработки: {e}")
            return exception_response(e)

    @api_v1.route("/recording/<recording_id>/post-processing", methods=["GET"])
    @require_api_key
    def get_recording_post_processing(recording_id: str) -> Any:
        """Получение статуса постобработки для конкретной записи."""
        try:
            callback = server.get_callback("get_post_processing_status")
            if callback:
                status = callback()
                return jsonify(
                    {
                        "success": True,
                        "recording_id": recording_id,
                        "data": status,
                    }
                )
            return internal_error_response()
        except Exception as e:
            logger.exception(
                f"Ошибка получения статуса постобработки записи {recording_id}: {e}"
            )
            return exception_response(e)
