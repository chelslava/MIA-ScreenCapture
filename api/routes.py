"""
Модуль маршрутов API
====================

Определяет REST API эндпоинты для видеозаписи с валидацией через Pydantic.
"""

import hashlib
from collections.abc import Callable
from typing import Any

from flask import current_app, g, jsonify, request
from pydantic import ValidationError
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from api.auth import require_api_key
from api.error_mapping import map_exception_to_api_error
from api.rate_limiter import rate_limit
from api.request_context import ensure_request_context
from api.routes_config import register_config_routes
from api.routes_recording import register_recording_routes
from api.routes_resources import (
    register_observability_routes,
    register_resource_routes,
)
from api.routes_schedule import register_schedule_routes
from api.runtime_models import APIOperation, APIOperationPayload
from logger_config import get_module_logger

logger = get_module_logger(__name__)


_ERROR_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    409: "conflict",
    413: "payload_too_large",
    429: "rate_limited",
}

_STOP_OPERATION_WAIT_SECONDS = 0.2
_IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
_IDEMPOTENCY_KEY_MAX_LENGTH = 128


def _get_trace_id() -> str:
    """Возвращает trace_id из контекста запроса или создаёт новый."""
    return str(ensure_request_context().trace_id)


def _standard_error_payload(
    code: str,
    message: str,
    details: Any | None = None,
) -> dict[str, Any]:
    """Формирует единый контракт ошибки API."""
    return {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details,
        },
        "trace_id": _get_trace_id(),
    }


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: Any | None = None,
) -> tuple[Any, int]:
    """Создаёт JSON-ответ в едином формате ошибки API."""
    response = jsonify(_standard_error_payload(code, message, details))
    response.status_code = status_code
    response.headers["X-Request-ID"] = _get_trace_id()
    return response, status_code


def _internal_error_response() -> tuple:
    """
    Возвращает безопасный ответ 500 без утечки внутренней ошибки.
    """
    return _error_response(
        500,
        "internal_error",
        "Внутренняя ошибка сервера",
    )


def _exception_response(error: Exception) -> tuple[Any, int]:
    """Преобразует исключение в стандартизированный API-ответ."""
    mapped = map_exception_to_api_error(error)
    return _error_response(
        mapped.status_code,
        mapped.code,
        mapped.message,
        mapped.details,
    )


def _extract_error_details(data: dict[str, Any]) -> Any | None:
    """Извлекает дополнительные детали из legacy error payload."""
    if "validation_errors" in data:
        return data["validation_errors"]
    if "rate_limit" in data:
        return data["rate_limit"]
    return None


def _normalize_error_payload(
    status_code: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Преобразует legacy error payload в единый контракт."""
    if status_code >= 500:
        return _standard_error_payload(
            "internal_error",
            "Внутренняя ошибка сервера",
        )

    if (
        data.get("success") is False
        and isinstance(data.get("error"), dict)
        and {"code", "message", "details"}.issubset(data["error"].keys())
    ):
        error_data = data["error"]
        return {
            "success": False,
            "error": {
                "code": error_data["code"],
                "message": error_data["message"],
                "details": error_data.get("details"),
            },
            "trace_id": data.get("trace_id") or _get_trace_id(),
        }

    error_value = data.get("error")
    message = (
        data.get("message") if isinstance(data.get("message"), str) else None
    )

    if status_code == 400 and "validation_errors" in data:
        return _standard_error_payload(
            "validation_error",
            message or "Ошибка валидации данных",
            data["validation_errors"],
        )

    code = _ERROR_CODE_BY_STATUS.get(status_code, "internal_error")

    if message is None and isinstance(error_value, str):
        message = error_value
    if message is None:
        message = "Ошибка запроса"

    return _standard_error_payload(code, message, _extract_error_details(data))


def _standardize_error_response(response):
    """Нормализует JSON-ошибки в единый контракт."""
    if response.status_code < 400 or not response.is_json:
        response.headers.setdefault("X-Request-ID", _get_trace_id())
        return response

    data = response.get_json(silent=True)
    if not isinstance(data, dict):
        response.headers.setdefault("X-Request-ID", _get_trace_id())
        return response

    payload = _normalize_error_payload(response.status_code, data)
    normalized = jsonify(payload)
    normalized.status_code = response.status_code
    normalized.headers["X-Request-ID"] = payload["trace_id"]
    return normalized


def _build_idempotency_fingerprint() -> str:
    """Формирует стабильный fingerprint входного запроса для dedup."""
    payload = request.get_data(cache=True, as_text=False) or b""
    source = b"|".join(
        [
            request.method.encode("utf-8"),
            request.path.encode("utf-8"),
            request.query_string or b"",
            payload,
        ]
    )
    return hashlib.sha256(source).hexdigest()


def _idempotency_response(
    status_code: int,
    code: str,
    message: str,
) -> tuple[Any, int]:
    """Формирует стандартизированный ответ по конфликту идемпотентности."""
    return _error_response(status_code, code, message)


def _execute_with_idempotency(
    server: Any,
    handler: Callable[[], Any],
) -> Any:
    """Выполняет write-операцию с учётом Idempotency-Key."""
    key = request.headers.get(_IDEMPOTENCY_KEY_HEADER, "").strip()
    if not key:
        return handler()

    if len(key) > _IDEMPOTENCY_KEY_MAX_LENGTH:
        return _error_response(
            400,
            "validation_error",
            (
                f"{_IDEMPOTENCY_KEY_HEADER} не должен превышать "
                f"{_IDEMPOTENCY_KEY_MAX_LENGTH} символов"
            ),
        )

    state = server.begin_idempotency_request(
        key, _build_idempotency_fingerprint()
    )
    state_name = state.get("state")
    if state_name == "conflict":
        return _idempotency_response(
            409,
            "idempotency_conflict",
            "Idempotency-Key уже использован для другого запроса",
        )
    if state_name == "in_progress":
        return _idempotency_response(
            409,
            "idempotency_in_progress",
            "Запрос с этим Idempotency-Key уже выполняется",
        )
    if state_name == "replay":
        replay = state.get("response") or {}
        response = current_app.response_class(
            replay.get("body_bytes", b""),
            status=int(replay.get("status_code", 200)),
            mimetype=str(replay.get("mimetype") or "application/json"),
        )
        response.headers["X-Idempotency-Replayed"] = "true"
        response.headers.setdefault("X-Request-ID", _get_trace_id())
        return response

    try:
        result = handler()
        response = current_app.make_response(result)
    except Exception:
        server.abort_idempotency_request(key)
        raise

    server.complete_idempotency_request(
        key=key,
        status_code=response.status_code,
        body_bytes=response.get_data(),
        mimetype=response.mimetype,
    )
    return response


def _parse_request_json() -> tuple[
    dict[str, Any] | None, tuple[Any, int] | None
]:
    """Безопасно парсит JSON тело запроса и возвращает ошибку при проблемах."""
    try:
        data = request.get_json(silent=False)
    except RequestEntityTooLarge:
        return (
            None,
            _error_response(
                413,
                "payload_too_large",
                "Слишком большой запрос",
            ),
        )
    except BadRequest:
        raw_payload = request.get_data(cache=True, as_text=False) or b""
        if not raw_payload:
            return {}, None
        return (
            None,
            _error_response(
                400,
                "bad_request",
                "Некорректный JSON в теле запроса",
            ),
        )

    if data is None:
        return {}, None

    if not isinstance(data, dict):
        return (
            None,
            _error_response(
                400,
                "validation_error",
                "Тело запроса должно быть JSON-объектом",
            ),
        )
    return data, None


def handle_validation_error(error: ValidationError) -> tuple:
    """
    Обработка ошибки валидации Pydantic.

    Args:
        error: Ошибка валидации Pydantic

    Returns:
        Кортеж (JSON ответ, HTTP код)
    """
    errors = []
    for err in error.errors():
        field = ".".join(str(loc) for loc in err["loc"])
        errors.append(
            {"field": field, "message": err["msg"], "type": err["type"]}
        )

    return _error_response(
        400,
        "validation_error",
        "Ошибка валидации данных",
        errors,
    )


def _serialize_operation(
    operation: dict[str, Any] | APIOperation,
) -> dict[str, Any]:
    """Преобразует внутреннее представление операции в API payload."""
    operation_model = (
        operation
        if isinstance(operation, APIOperation)
        else APIOperation.from_dict(operation)
    )
    return APIOperationPayload.from_operation(operation_model).to_dict()


def _background_operation_status_response(
    operation: dict[str, Any] | None,
) -> tuple[Any, int]:
    """Формирует ответ с состоянием фоновой операции."""
    if operation is None:
        return _error_response(
            404,
            "not_found",
            "Операция не найдена",
        )
    return jsonify(
        {
            "success": True,
            "data": _serialize_operation(operation),
        }
    ), 200


def _stop_operation_response(
    server: Any,
) -> tuple[Any, int]:
    """Запускает остановку записи и возвращает синхронный или фоновой ответ."""
    request_context = ensure_request_context()
    callback = server.get_callback("stop")
    if callback is None:
        return _internal_error_response()

    operation = server.submit_background_operation(
        "stop",
        callback,
        request_id=request_context.request_id,
        trace_id=request_context.trace_id,
        client_ip=request_context.client_ip,
    )
    operation_id = operation.get("id")
    if not operation_id:
        return _internal_error_response()

    completed = server.wait_for_background_operation(
        operation_id,
        _STOP_OPERATION_WAIT_SECONDS,
    )
    if completed is None:
        return _error_response(
            500,
            "internal_error",
            "Не удалось отследить состояние операции",
        )

    if completed.get("status") == "running":
        return (
            jsonify(
                {
                    "success": True,
                    "data": _serialize_operation(completed),
                }
            ),
            202,
        )

    if completed.get("status") == "failed":
        return _error_response(
            500,
            "internal_error",
            str(completed.get("error") or "Не удалось остановить запись"),
        )

    result = completed.get("result")
    if isinstance(result, dict):
        payload_data = dict(result)
    elif result is None:
        payload_data = {}
    else:
        payload_data = {"value": result}
    payload_data["operation_id"] = completed.get("id")
    payload_data["status"] = completed.get("status")
    if completed.get("request_id") is not None:
        payload_data["request_id"] = completed.get("request_id")
    if completed.get("trace_id") is not None:
        payload_data["trace_id"] = completed.get("trace_id")
    if completed.get("client_ip") is not None:
        payload_data["client_ip"] = completed.get("client_ip")
    return jsonify(
        {"success": payload_data.get("success", True), "data": payload_data}
    ), 200


def _register_request_hooks(app: Any, server: Any) -> None:
    """Регистрирует before/after request hooks API."""

    @app.before_request
    def set_server_context() -> None:
        """Установка server в контекст запроса для декораторов."""
        g.server = server
        g.request_id = ensure_request_context().request_id

    @app.after_request
    def standardize_error_responses(response: Any) -> Any:
        """Приведение legacy error payload к единому контракту."""
        return _standardize_error_response(response)


def _register_health_route(app: Any, server: Any) -> None:
    """Регистрирует endpoint проверки здоровья."""

    @app.route("/health", methods=["GET"])
    def health_check() -> Any:
        """Эндпоинт проверки здоровья."""
        response = jsonify(server._get_health_payload())
        response.headers["X-Request-ID"] = _get_trace_id()
        return response


def _register_legacy_routes(
    app: Any,
    *,
    get_status: Any,
    start_recording: Any,
    stop_recording: Any,
    pause_recording: Any,
) -> None:
    """Регистрирует legacy API routes для обратной совместимости."""

    @app.route("/api/status", methods=["GET"])
    @require_api_key
    def legacy_get_status() -> Any:
        """Legacy endpoint для обратной совместимости."""
        return get_status()

    @app.route("/api/start", methods=["POST"])
    @rate_limit
    @require_api_key
    def legacy_start_recording() -> Any:
        """Legacy endpoint для обратной совместимости."""
        return start_recording()

    @app.route("/api/stop", methods=["POST"])
    @rate_limit
    @require_api_key
    def legacy_stop_recording() -> Any:
        """Legacy endpoint для обратной совместимости."""
        return stop_recording()

    @app.route("/api/pause", methods=["POST"])
    @rate_limit
    @require_api_key
    def legacy_toggle_pause() -> Any:
        """Legacy endpoint для обратной совместимости."""
        return pause_recording()


def _register_status_routes(api_v1: Any, server: Any) -> Any:
    """Регистрирует маршруты состояния API."""

    @api_v1.route("/status", methods=["GET"])
    @require_api_key
    def get_status() -> Any:
        """Получение текущего статуса записи."""
        try:
            callback = server.get_callback("status")
            if callback:
                status = callback()
                return jsonify({"success": True, "data": status})
            return _internal_error_response()
        except Exception as e:
            logger.exception(f"Ошибка получения статуса: {e}")
            return _exception_response(e)

    @api_v1.route("operations/<operation_id>", methods=["GET"])
    @require_api_key
    def get_operation_status(operation_id: str) -> Any:
        """Получение статуса фоновой операции."""
        try:
            operation = server.get_background_operation(operation_id)
            return _background_operation_status_response(operation)
        except Exception as e:
            logger.exception(f"Ошибка получения статуса операции: {e}")
            return _exception_response(e)

    return get_status


def _register_recording_routes(
    api_v1: Any,
    server: Any,
) -> tuple[Any, Any, Any]:
    """Регистрирует маршруты управления записью."""
    return register_recording_routes(
        api_v1,
        server,
        logger=logger,
        parse_request_json=_parse_request_json,
        handle_validation_error=handle_validation_error,
        execute_with_idempotency=_execute_with_idempotency,
        stop_operation_response=_stop_operation_response,
        internal_error_response=_internal_error_response,
        exception_response=_exception_response,
        error_response=_error_response,
    )


def _register_schedule_routes(api_v1: Any, server: Any) -> None:
    """Регистрирует маршруты планировщика."""
    return register_schedule_routes(
        api_v1,
        server,
        logger=logger,
        parse_request_json=_parse_request_json,
        handle_validation_error=handle_validation_error,
        execute_with_idempotency=_execute_with_idempotency,
        internal_error_response=_internal_error_response,
        exception_response=_exception_response,
    )


def _register_resource_routes(api_v1: Any, server: Any) -> None:
    """Регистрирует маршруты ресурсов окружения."""
    return register_resource_routes(
        api_v1,
        server,
        logger=logger,
        internal_error_response=_internal_error_response,
        exception_response=_exception_response,
    )


def _register_config_routes(api_v1: Any, server: Any) -> None:
    """Регистрирует маршруты конфигурации."""
    return register_config_routes(
        api_v1,
        server,
        logger=logger,
        parse_request_json=_parse_request_json,
        handle_validation_error=handle_validation_error,
        execute_with_idempotency=_execute_with_idempotency,
        internal_error_response=_internal_error_response,
        exception_response=_exception_response,
    )


def _register_observability_routes(api_v1: Any, server: Any) -> None:
    """Регистрирует маршруты observability."""
    return register_observability_routes(
        api_v1,
        server,
        logger=logger,
        exception_response=_exception_response,
    )


def register_routes(app, server) -> None:
    """
    Регистрация всех маршрутов API с Flask приложением.

    Args:
        app: Экземпляр Flask приложения
        server: Экземпляр APIServer для обратных вызовов
    """
    from api.swagger import register_swagger_routes

    # Регистрация Swagger документации
    register_swagger_routes(app)
    _register_request_hooks(app, server)

    # Создаём Blueprint для API v1
    from flask import Blueprint

    api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")
    _register_health_route(app, server)
    get_status = _register_status_routes(api_v1, server)
    start_recording, stop_recording, pause_recording = (
        _register_recording_routes(api_v1, server)
    )
    _register_schedule_routes(api_v1, server)
    _register_resource_routes(api_v1, server)
    _register_config_routes(api_v1, server)
    _register_observability_routes(api_v1, server)

    # Регистрация Blueprint
    app.register_blueprint(api_v1)

    _register_legacy_routes(
        app,
        get_status=get_status,
        start_recording=start_recording,
        stop_recording=stop_recording,
        pause_recording=pause_recording,
    )

    logger.info("Маршруты API зарегистрированы (v1 + legacy)")
