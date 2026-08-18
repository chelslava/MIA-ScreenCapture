"""
Маршруты REST API для авто-обновления приложения (#128).
======================================================
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from api.routes import _error_response, _execute_with_idempotency
from api.schemas import (
    CheckUpdateApiRequest,
    DownloadUpdateApiRequest,
    UpdateAppConfigRequest,
)
from logger_config import get_module_logger

if TYPE_CHECKING:
    from api.server import APIServer

logger = get_module_logger(__name__)


def create_updates_blueprint(server: APIServer) -> Blueprint:
    """Создает Blueprint с маршрутами авто-обновления."""
    bp = Blueprint("updates", __name__, url_prefix="/api/v1/updates")

    @bp.route("/config", methods=["GET"])
    def get_update_config() -> Any:
        """Получить текущие настройки авто-обновлений."""
        handler = server.get_callback("get_update_config")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )
        try:
            cfg = handler()
            return jsonify({"success": True, "data": cfg}), 200
        except Exception as e:
            logger.error("Ошибка при получении настроек обновлений: %s", e)
            return _error_response(500, "internal_error", str(e))

    @bp.route("/config", methods=["PUT"])
    def update_update_config() -> Any:
        """Обновить настройки авто-обновлений."""
        handler = server.get_callback("update_update_config")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )

        json_data = request.get_json() or {}
        try:
            req = UpdateAppConfigRequest.model_validate(json_data)
        except ValidationError as e:
            return _error_response(
                400,
                "validation_error",
                "Некорректные параметры настроек",
                details=[
                    {"field": str(err["loc"]), "message": err["msg"]}
                    for err in e.errors()
                ],
            )

        data_to_update = {
            k: v for k, v in req.model_dump().items() if v is not None
        }

        def _do_update() -> Any:
            try:
                res = handler(data_to_update)
                if not res.get("success", False):
                    return _error_response(
                        400,
                        "update_error",
                        res.get("error", "Не удалось сохранить настройки"),
                    )
                return jsonify(
                    {"success": True, "data": res.get("config")}
                ), 200
            except Exception as ex:
                logger.error(
                    "Ошибка при сохранении настроек обновлений: %s", ex
                )
                return _error_response(500, "internal_error", str(ex))

        return _execute_with_idempotency(server, _do_update)

    @bp.route("/check", methods=["GET", "POST"])
    def check_for_updates() -> Any:
        """Проверить наличие новой версии приложения."""
        handler = server.get_callback("check_for_updates")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )

        force = False
        if request.method == "POST":
            json_data = request.get_json() or {}
            try:
                req = CheckUpdateApiRequest.model_validate(json_data)
                force = req.force
            except ValidationError as e:
                return _error_response(
                    400,
                    "validation_error",
                    "Некорректные параметры запроса проверки",
                    details=[
                        {"field": str(err["loc"]), "message": err["msg"]}
                        for err in e.errors()
                    ],
                )
        else:
            force = request.args.get("force", "false").lower() in ("true", "1")

        try:
            res = handler(force=force)
            return jsonify({"success": True, "data": res}), 200
        except Exception as e:
            logger.error("Ошибка при проверке обновлений: %s", e)
            return _error_response(500, "internal_error", str(e))

    @bp.route("/download", methods=["POST"])
    def download_update() -> Any:
        """Запустить скачивание обновления."""
        handler = server.get_callback("download_update")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )

        json_data = request.get_json() or {}
        try:
            req = DownloadUpdateApiRequest.model_validate(json_data)
        except ValidationError as e:
            return _error_response(
                400,
                "validation_error",
                "Некорректные параметры запроса скачивания",
                details=[
                    {"field": str(err["loc"]), "message": err["msg"]}
                    for err in e.errors()
                ],
            )

        def _do_download() -> Any:
            try:
                res = handler(version=req.version)
                if not res.get("success", False):
                    return _error_response(
                        400,
                        "download_error",
                        res.get("error", "Не удалось запустить скачивание"),
                    )
                return jsonify(res), 200
            except Exception as ex:
                logger.error("Ошибка при скачивании обновления: %s", ex)
                return _error_response(500, "internal_error", str(ex))

        return _execute_with_idempotency(server, _do_download)

    @bp.route("/apply", methods=["POST"])
    def apply_update() -> Any:
        """Применить скачанное обновление."""
        handler = server.get_callback("apply_update")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )

        def _do_apply() -> Any:
            try:
                res = handler()
                if not res.get("success", False):
                    return _error_response(
                        400,
                        "apply_error",
                        res.get("error", "Не удалось запустить обновление"),
                    )
                return jsonify(res), 200
            except Exception as ex:
                logger.error("Ошибка при применении обновления: %s", ex)
                return _error_response(500, "internal_error", str(ex))

        return _execute_with_idempotency(server, _do_apply)

    @bp.route("/status", methods=["GET"])
    def get_update_status() -> Any:
        """Получить текущий статус подсистемы авто-обновления."""
        handler = server.get_callback("get_update_status")
        if not handler:
            return _error_response(
                501, "not_implemented", "Callback не зарегистрирован"
            )
        try:
            st = handler()
            return jsonify({"success": True, "data": st}), 200
        except Exception as e:
            logger.error("Ошибка при получении статуса обновлений: %s", e)
            return _error_response(500, "internal_error", str(e))

    return bp
