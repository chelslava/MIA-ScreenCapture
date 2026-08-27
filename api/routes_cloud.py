"""
Маршруты REST API для управления облачной синхронизацией (Issue #54).
====================================================================
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import jsonify
from werkzeug.exceptions import BadRequest

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from logger_config import get_module_logger

logger = get_module_logger(__name__)


def register_cloud_routes(
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
    """Регистрирует маршруты облачной синхронизации."""

    @api_v1.route("/cloud/status", methods=["GET"])
    @require_api_key
    def get_cloud_status() -> Any:
        """Получение статуса облачной синхронизации."""
        try:
            callback = server.get_callback("get_cloud_status")
            if callback:
                status = callback()
                return jsonify({"success": True, "data": status}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка при получении статуса облака: %s", e)
            return exception_response(e)

    @api_v1.route("/cloud/config", methods=["POST"])
    @rate_limit
    @require_api_key
    def configure_cloud() -> Any:
        """Настройка параметров облачного хранилища."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            provider = data.get("provider", "s3")
            credentials = data.get("credentials", {})
            auto_sync = bool(data.get("auto_sync", False))
            min_file_size_mb = float(data.get("min_file_size_mb", 0.0))
            remote_folder = data.get("remote_folder", "Recordings")

            callback = server.get_callback("configure_cloud")
            if callback:
                success = callback(
                    provider=provider,
                    credentials=credentials,
                    auto_sync=auto_sync,
                    min_file_size_mb=min_file_size_mb,
                    remote_folder=remote_folder,
                )
                if not success:
                    return error_response(
                        400,
                        "configuration_failed",
                        f"Не удалось настроить провайдер {provider}",
                    )
                return jsonify({"success": True, "provider": provider}), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при настройке облака: %s", e)
            return exception_response(e)

    @api_v1.route("/cloud/test", methods=["POST"])
    @rate_limit
    @require_api_key
    def test_cloud_connection() -> Any:
        """Тест соединения с облачным провайдером."""
        try:
            callback = server.get_callback("test_cloud_connection")
            if callback:
                connected = callback()
                return jsonify({"success": True, "connected": connected}), 200
            return internal_error_response()
        except Exception as e:
            logger.exception("Ошибка при тесте соединения с облаком: %s", e)
            return exception_response(e)

    @api_v1.route("/cloud/sync", methods=["POST"])
    @rate_limit
    @require_api_key
    def sync_cloud_files() -> Any:
        """Постановка файлов в очередь облачной синхронизации."""
        try:
            data, parse_error = parse_request_json()
            if parse_error is not None:
                return parse_error
            assert data is not None

            file_paths = data.get("file_paths", [])
            if isinstance(file_paths, str):
                file_paths = [file_paths]

            callback = server.get_callback("queue_cloud_sync")
            if callback:
                queued = 0
                for fp in file_paths:
                    if callback(Path(fp)):
                        queued += 1
                return jsonify({"success": True, "queued": queued}), 200
            return internal_error_response()
        except BadRequest as e:
            return error_response(400, "bad_request", str(e))
        except Exception as e:
            logger.exception("Ошибка при постановке файлов в очередь: %s", e)
            return exception_response(e)
