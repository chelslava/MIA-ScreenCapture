"""Доменные маршруты API для профилей записи (Issue #117)."""

from __future__ import annotations

from typing import Any

from flask import jsonify
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import (
    CreateProfileRequest,
    ImportProfileRequest,
    UpdateProfileRequest,
)


def register_profiles_routes(
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
    """Регистрирует маршруты управления профилями записи."""

    @api_v1.route("/profiles", methods=["GET"])
    @require_api_key
    def get_profiles() -> Any:
        """Получение списка всех профилей записи."""
        try:
            callback = server.get_callback("get_profiles")
            if callback:
                profiles = callback()
                return jsonify({"success": True, "data": profiles})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения списка профилей: {e}")
            return exception_response(e)

    @api_v1.route("/profiles", methods=["POST"])
    @rate_limit
    @require_api_key
    def create_profile() -> Any:
        """Создание нового профиля записи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = CreateProfileRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback = server.get_callback("create_profile")
                if callback:
                    result = callback(validated.model_dump(exclude_none=True))
                    if result.get("success"):
                        return (
                            jsonify(
                                {
                                    "success": True,
                                    "data": result.get("profile"),
                                }
                            ),
                            201,
                        )
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "bad_request",
                                    "message": result.get(
                                        "error", "Не удалось создать профиль"
                                    ),
                                    "details": None,
                                },
                            }
                        ),
                        400,
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка создания профиля: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/<profile_id>", methods=["GET"])
    @require_api_key
    def get_profile(profile_id: str) -> Any:
        """Получение деталей конкретного профиля."""
        try:
            callback = server.get_callback("get_profile")
            if callback:
                profile = callback(profile_id)
                if profile is None:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "not_found",
                                    "message": f"Профиль '{profile_id}' не найден",
                                    "details": None,
                                },
                            }
                        ),
                        404,
                    )
                return jsonify({"success": True, "data": profile})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения профиля {profile_id}: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/<profile_id>", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_profile(profile_id: str) -> Any:
        """Обновление существующего профиля записи."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = UpdateProfileRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback = server.get_callback("update_profile")
                if callback:
                    result = callback(
                        profile_id, validated.model_dump(exclude_none=True)
                    )
                    if result.get("success"):
                        return jsonify(
                            {
                                "success": True,
                                "data": result.get("profile"),
                            }
                        )
                    status_code = (
                        404 if "не найден" in result.get("error", "") else 400
                    )
                    code = "not_found" if status_code == 404 else "bad_request"
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": code,
                                    "message": result.get(
                                        "error", "Не удалось обновить профиль"
                                    ),
                                    "details": None,
                                },
                            }
                        ),
                        status_code,
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка обновления профиля {profile_id}: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/<profile_id>", methods=["DELETE"])
    @rate_limit
    @require_api_key
    def delete_profile(profile_id: str) -> Any:
        """Удаление профиля записи."""
        try:

            def _handler() -> Any:
                callback = server.get_callback("delete_profile")
                if callback:
                    result = callback(profile_id)
                    if result.get("success"):
                        return jsonify(
                            {
                                "success": True,
                                "data": {"deleted": profile_id},
                            }
                        )
                    error_msg = result.get(
                        "error", "Не удалось удалить профиль"
                    )
                    status_code = 404 if "не найден" in error_msg else 400
                    code = "not_found" if status_code == 404 else "bad_request"
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": code,
                                    "message": error_msg,
                                    "details": None,
                                },
                            }
                        ),
                        status_code,
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка удаления профиля {profile_id}: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/<profile_id>/apply", methods=["POST"])
    @rate_limit
    @require_api_key
    def apply_profile(profile_id: str) -> Any:
        """Применение настроек профиля к активной конфигурации."""
        try:

            def _handler() -> Any:
                callback = server.get_callback("apply_profile")
                if callback:
                    result = callback(profile_id)
                    if result.get("success"):
                        return jsonify(
                            {
                                "success": True,
                                "data": result.get("applied_profile"),
                            }
                        )
                    error_msg = result.get(
                        "error", "Не удалось применить профиль"
                    )
                    status_code = 404 if "не найден" in error_msg else 400
                    code = "not_found" if status_code == 404 else "bad_request"
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": code,
                                    "message": error_msg,
                                    "details": None,
                                },
                            }
                        ),
                        status_code,
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка применения профиля {profile_id}: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/<profile_id>/export", methods=["GET"])
    @require_api_key
    def export_profile(profile_id: str) -> Any:
        """Экспорт профиля в JSON-структуру."""
        try:
            callback = server.get_callback("export_profile")
            if callback:
                exported = callback(profile_id)
                if exported is None:
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "not_found",
                                    "message": f"Профиль '{profile_id}' не найден",
                                    "details": None,
                                },
                            }
                        ),
                        404,
                    )
                return jsonify({"success": True, "data": exported})
            return internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка экспорта профиля {profile_id}: {e}")
            return exception_response(e)

    @api_v1.route("/profiles/import", methods=["POST"])
    @rate_limit
    @require_api_key
    def import_profile() -> Any:
        """Импорт профиля из JSON-структуры."""
        try:

            def _handler() -> Any:
                data, parse_error = parse_request_json()
                if parse_error is not None:
                    return parse_error
                assert data is not None

                try:
                    validated = ImportProfileRequest(**data)
                except ValidationError as e:
                    return handle_validation_error(e)

                callback = server.get_callback("import_profile")
                if callback:
                    result = callback(validated.model_dump(exclude_none=True))
                    if result.get("success"):
                        return (
                            jsonify(
                                {
                                    "success": True,
                                    "data": result.get("profile"),
                                }
                            ),
                            201,
                        )
                    return (
                        jsonify(
                            {
                                "success": False,
                                "error": {
                                    "code": "bad_request",
                                    "message": result.get(
                                        "error",
                                        "Не удалось импортировать профиль",
                                    ),
                                    "details": None,
                                },
                            }
                        ),
                        400,
                    )
                return internal_error_response()

            return execute_with_idempotency(server, _handler)
        except Exception as e:
            logger.exception(f"Ошибка импорта профиля: {e}")
            return exception_response(e)
