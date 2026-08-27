"""
Доменные маршруты REST API для библиотеки записей (Issue #119).
==============================================================

Предоставляет эндпоинты:
- GET    /api/v1/library           — список записей с фильтрами;
- GET    /api/v1/library/tags      — список всех тегов;
- POST   /api/v1/library/tags      — добавление тега к записи;
- DELETE /api/v1/library/tags      — удаление тега из записи;
- DELETE /api/v1/library/recording — удаление записи.
"""

from __future__ import annotations

from typing import Any

from flask import jsonify, request
from werkzeug.exceptions import BadRequest

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from logger_config import get_module_logger

logger = get_module_logger(__name__)


def register_library_routes(
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
    """Регистрирует маршруты библиотеки записей."""

    @api_v1.route("/library", methods=["GET"])
    @require_api_key
    def list_library_items() -> Any:
        """Получение списка видеозаписей библиотеки."""
        try:
            query = request.args.get("query")
            tag = request.args.get("tag")
            sort_by = request.args.get("sort_by", "date")
            sort_desc = request.args.get("sort_desc", "true").lower() in (
                "true",
                "1",
            )

            callback = server.get_callback("get_library_items")
            if callback:
                items = callback(
                    query=query, tag=tag, sort_by=sort_by, sort_desc=sort_desc
                )
                return jsonify({"success": True, "data": items}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception(
                "Ошибка получения списка записей библиотеки: %s", e
            )
            return exception_response(e)

    @api_v1.route("/library/tags", methods=["GET"])
    @require_api_key
    def list_library_tags() -> Any:
        """Получение списка всех тегов."""
        try:
            callback = server.get_callback("get_library_tags")
            if callback:
                tags = callback()
                return jsonify({"success": True, "data": tags}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка получения списка тегов: %s", e)
            return exception_response(e)

    @api_v1.route("/library/tags", methods=["POST"])
    @rate_limit
    @require_api_key
    def add_library_tag() -> Any:
        """Добавление тега к записи."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            path = data.get("path")
            tag = data.get("tag")
            if not path or not tag:
                return error_response(
                    400, "bad_request", "Требуются параметры 'path' и 'tag'"
                )

            callback = server.get_callback("add_library_tag")
            if callback:
                success = callback(path, tag)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось добавить тег к {path}",
                    )
                return jsonify(
                    {"success": True, "message": f"Тег '{tag}' добавлен"}
                ), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при добавлении тега: %s", e)
            return exception_response(e)

    @api_v1.route("/library/tags", methods=["DELETE"])
    @rate_limit
    @require_api_key
    def remove_library_tag() -> Any:
        """Удаление тега из записи."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            path = data.get("path")
            tag = data.get("tag")
            if not path or not tag:
                return error_response(
                    400, "bad_request", "Требуются параметры 'path' и 'tag'"
                )

            callback = server.get_callback("remove_library_tag")
            if callback:
                success = callback(path, tag)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось удалить тег из {path}",
                    )
                return jsonify(
                    {"success": True, "message": f"Тег '{tag}' удалён"}
                ), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при удалении тега: %s", e)
            return exception_response(e)

    @api_v1.route("/library/recording", methods=["DELETE"])
    @rate_limit
    @require_api_key
    def delete_library_recording() -> Any:
        """Удаление записи из библиотеки."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            path = data.get("path")
            delete_file = bool(data.get("delete_file", True))
            if not path:
                return error_response(
                    400, "bad_request", "Требуется параметр 'path'"
                )

            callback = server.get_callback("delete_library_recording")
            if callback:
                success = callback(path, delete_file=delete_file)
                if not success:
                    return error_response(
                        400,
                        "operation_failed",
                        f"Не удалось удалить запись {path}",
                    )
                return jsonify(
                    {"success": True, "message": f"Запись {path} удалена"}
                ), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при удалении записи: %s", e)
            return exception_response(e)
