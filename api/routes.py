"""
Модуль маршрутов API
====================

Определяет REST API эндпоинты для видеозаписи с валидацией через Pydantic.
"""

from datetime import datetime
from functools import wraps
import uuid
from typing import Any, Callable, Optional

from flask import g, jsonify, request
from pydantic import ValidationError

from api.auth import require_api_key
from api.rate_limiter import rate_limit
from api.schemas import (
    CreateScheduleRequest,
    StartRecordingRequest,
    ToggleScheduleRequest,
    UpdateConfigRequest,
    UpdateScheduleRequest,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


_ERROR_CODE_BY_STATUS = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    429: "rate_limited",
}


def _get_trace_id() -> str:
    """Возвращает trace_id из контекста запроса или создаёт новый."""
    trace_id = getattr(g, "trace_id", None)
    if trace_id:
        return trace_id

    trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
    g.trace_id = trace_id
    return trace_id


def _standard_error_payload(
    code: str,
    message: str,
    details: Optional[Any] = None,
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
    details: Optional[Any] = None,
) -> tuple:
    """Создаёт JSON-ответ в едином формате ошибки API."""
    response = jsonify(_standard_error_payload(code, message, details))
    response.status_code = status_code
    response.headers["X-Request-ID"] = _get_trace_id()
    return response


def _internal_error_response() -> tuple:
    """
    Возвращает безопасный ответ 500 без утечки внутренней ошибки.
    """
    return _error_response(
        500,
        "internal_error",
        "Внутренняя ошибка сервера",
    )


def _extract_error_details(data: dict[str, Any]) -> Optional[Any]:
    """Извлекает дополнительные детали из legacy error payload."""
    if "validation_errors" in data:
        return data["validation_errors"]
    if "rate_limit" in data:
        return data["rate_limit"]

    details = {
        key: value
        for key, value in data.items()
        if key
        not in {
            "success",
            "error",
            "message",
            "trace_id",
        }
    }
    return details or None


def _normalize_error_payload(
    status_code: int,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Преобразует legacy error payload в единый контракт."""
    if (
        data.get("success") is False
        and isinstance(data.get("error"), dict)
        and {"code", "message", "details"}.issubset(data["error"].keys())
    ):
        payload = dict(data)
        payload.setdefault("trace_id", _get_trace_id())
        return payload

    error_value = data.get("error")
    message = (
        data.get("message")
        if isinstance(data.get("message"), str)
        else None
    )

    if status_code == 400 and "validation_errors" in data:
        return _standard_error_payload(
            "validation_error",
            message or "Ошибка валидации данных",
            data["validation_errors"],
        )

    code = _ERROR_CODE_BY_STATUS.get(status_code, "internal_error")
    if status_code >= 500:
        code = "internal_error"

    if message is None and isinstance(error_value, str):
        message = error_value
    if message is None:
        message = "Внутренняя ошибка сервера" if status_code >= 500 else "Ошибка запроса"

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


# TODO: Декораторы api_endpoint и api_callback подготовлены для рефакторинга
# обработки API запросов. Применить к endpoints после завершения текущих изменений.


def api_endpoint(
    callback_name: str,
    error_message: str = "Ошибка выполнения запроса",
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Декоратор для стандартизации обработки API запросов.

    Автоматически обрабатывает:
    - Получение callback из server
    - Обработку ValidationError
    - Логирование ошибок
    - Форматирование ответов

    Args:
        callback_name: Имя callback для получения из server
        error_message: Сообщение об ошибке для логирования

    Returns:
        Декоратор для функции-обработчика

    Example:
        @app.route("/api/status", methods=["GET"])
        @require_api_key
        @api_endpoint("status", "Ошибка получения статуса")
        def get_status(callback):
            return callback()
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                # Получаем server из замыкания (передаётся через kwargs)
                server_instance = kwargs.get("server")
                if not server_instance:
                    # Пытаемся получить из первого аргумента
                    # (для функций внутри register_routes)
                    return func(*args, **kwargs)

                callback = server_instance.get_callback(callback_name)
                if not callback:
                    return jsonify(
                        {
                            "success": False,
                            "error": f"Обратный вызов {callback_name} не установлен",
                        }
                    ), 500

                # Передаём callback в функцию
                return func(*args, callback=callback, **kwargs)

            except ValidationError as e:
                return handle_validation_error(e)
            except Exception as e:
                logger.exception(f"{error_message}: {e}")
                return _internal_error_response()

        return wrapper

    return decorator


def api_callback(
    callback_name: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """
    Упрощённый декоратор для endpoints, которые просто вызывают callback.

    Для простых endpoints без дополнительной логики.

    Args:
        callback_name: Имя callback для получения из server

    Note:
        Требует установки g.server в before_request middleware.
        См. register_routes для примера установки.

    Example:
        @app.route("/api/status", methods=["GET"])
        @require_api_key
        @api_callback("status")
        def get_status():
            pass  # callback будет вызван автоматически
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Извлекаем server из контекста Flask (глобальная переменная)
            from flask import g

            server_instance = getattr(g, "server", None)
            if not server_instance:
                logger.error(
                    "g.server не установлен. Добавьте @app.before_request "
                    "для установки g.server"
                )
                return jsonify(
                    {
                        "success": False,
                        "error": "Сервер не инициализирован",
                    }
                ), 500

            callback = server_instance.get_callback(callback_name)
            if not callback:
                return jsonify(
                    {
                        "success": False,
                        "error": f"Обратный вызов {callback_name} не установлен",
                    }
                ), 500

            try:
                result = callback()
                return jsonify({"success": True, "data": result})
            except ValidationError as e:
                return handle_validation_error(e)
            except Exception as e:
                logger.exception(f"Ошибка в {callback_name}: {e}")
                return _internal_error_response()

        return wrapper

    return decorator


def register_routes(app, server) -> None:
    """
    Регистрация всех маршрутов API с Flask приложением.

    Args:
        app: Экземпляр Flask приложения
        server: Экземпляр APIServer для обратных вызовов
    """
    from flask import g

    from api.swagger import register_swagger_routes

    # Регистрация Swagger документации
    register_swagger_routes(app)

    @app.before_request
    def set_server_context() -> None:
        """Установка server в контекст запроса для декораторов."""
        g.server = server
        _get_trace_id()

    @app.after_request
    def standardize_error_responses(response):
        """Приведение legacy error payload к единому контракту."""
        return _standardize_error_response(response)

    @app.route("/api/status", methods=["GET"])
    @require_api_key
    def get_status():
        """
        Получение текущего статуса записи.

        Returns:
            JSON с информацией о статусе записи
        """
        try:
            callback = server.get_callback("status")
            if callback:
                status = callback()
                return jsonify({"success": True, "data": status})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов статуса не установлен",
                }
            ), 500
        except Exception as e:
            logger.exception(f"Ошибка получения статуса: {e}")
            return _internal_error_response()

    @app.route("/api/start", methods=["POST"])
    @rate_limit
    @require_api_key
    def start_recording():
        """
        Начало новой записи.

        Тело запроса (JSON):
            - area: "full" | "window" | "rect"
            - window_title: str (опционально, для режима окна)
            - rect: [x1, y1, x2, y2] (опционально, для режима прямоугольника)
            - audio: "mic" | "system" | "none" | "both"
            - output_path: str (опционально)
            - fps: int (опционально, 1-120)
            - codec: str (опционально)
            - bitrate: str (опционально, формат: 2M, 5000K)
            - duration: int (опционально, секунды)

        Returns:
            JSON с ID записи или ошибкой
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = StartRecordingRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            # Преобразование в словарь для обратного вызова
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

            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов запуска не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка начала записи: {e}")
            return _internal_error_response()

    @app.route("/api/stop", methods=["POST"])
    @rate_limit
    @require_api_key
    def stop_recording():
        """
        Остановка текущей записи.

        Returns:
            JSON с результатом
        """
        try:
            callback = server.get_callback("stop")
            if callback:
                result = callback()
                return jsonify(
                    {"success": result.get("success", True), "data": result}
                )
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов остановки не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка остановки записи: {e}")
            return _internal_error_response()

    @app.route("/api/pause", methods=["POST"])
    @rate_limit
    @require_api_key
    def pause_recording():
        """
        Пауза или возобновление текущей записи.

        Returns:
            JSON с новым состоянием паузы
        """
        try:
            callback = server.get_callback("pause")
            if callback:
                result = callback()
                return jsonify({"success": True, "data": result})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов паузы не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка паузы записи: {e}")
            return _internal_error_response()

    @app.route("/api/recordings", methods=["GET"])
    @require_api_key
    def get_recordings():
        """
        Получение списка недавних записей.

        Returns:
            JSON со списком записей
        """
        try:
            callback = server.get_callback("recordings")
            if callback:
                recordings = callback()
                return jsonify({"success": True, "data": recordings})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов записей не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка получения записей: {e}")
            return _internal_error_response()

    @app.route("/api/events/recent", methods=["GET"])
    @require_api_key
    def get_recent_events():
        """
        Получение недавних real-time событий записи.

        Query параметры:
            - limit: int (1..500), опционально, по умолчанию 50
        """
        try:
            limit_raw = request.args.get("limit", "50")
            try:
                limit = int(limit_raw)
            except ValueError:
                return _error_response(
                    400, "validation_error", "Параметр limit должен быть числом"
                )

            manager = server.get_websocket_manager()
            if manager is None:
                return jsonify({"success": True, "data": []})

            events = manager.get_recent_events(limit=limit)
            return jsonify({"success": True, "data": events})
        except Exception as e:
            logger.exception(f"Ошибка получения событий: {e}")
            return _internal_error_response()

    @app.route("/api/events/stats", methods=["GET"])
    @require_api_key
    def get_events_stats():
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
            return _internal_error_response()

    @app.route("/api/schedule", methods=["GET"])
    @require_api_key
    def get_schedule():
        """
        Получение списка запланированных задач.

        Returns:
            JSON со списком задач
        """
        try:
            callback = server.get_callback("get_schedule")
            if callback:
                tasks = callback()
                return jsonify({"success": True, "data": tasks})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов расписания не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка получения расписания: {e}")
            return _internal_error_response()

    @app.route("/api/schedule", methods=["POST"])
    @rate_limit
    @require_api_key
    def create_schedule():
        """
        Создание новой запланированной задачи.

        Тело запроса (JSON):
            - name: str (название задачи)
            - trigger: "once" | "daily" | "weekly" | "interval"
            - datetime: str (формат ISO, для once)
            - time: str "HH:MM" (для daily/weekly)
            - day_of_week: str "0,1,2,3,4" (для weekly, 0=Понедельник)
            - hours: int (для interval)
            - minutes: int (для interval)
            - params: { параметры записи }

        Returns:
            JSON с ID задачи
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = CreateScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            # Преобразование в словарь для обратного вызова
            callback_data = validated.model_dump(exclude_none=True)

            # Преобразование params если есть
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

            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов создания расписания не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка создания расписания: {e}")
            return _internal_error_response()

    @app.route("/api/schedule/<task_id>", methods=["DELETE"])
    @rate_limit
    @require_api_key
    def delete_schedule(task_id: str):
        """
        Удаление запланированной задачи.

        Args:
            task_id: ID задачи для удаления

        Returns:
            JSON с результатом
        """
        try:
            callback = server.get_callback("delete_schedule")
            if callback:
                result = callback(task_id)
                return jsonify(
                    {"success": result.get("success", True), "data": result}
                )
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов удаления расписания не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка удаления расписания: {e}")
            return _internal_error_response()

    @app.route("/api/schedule/<task_id>", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_schedule(task_id: str):
        """
        Обновление запланированной задачи.

        Args:
            task_id: ID задачи для обновления

        Тело запроса (JSON):
            Поля задачи для обновления

        Returns:
            JSON с результатом
        """
        try:
            data = request.get_json() or {}
            data["id"] = task_id

            # Валидация входных данных
            try:
                validated = UpdateScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback_data = validated.model_dump(exclude_none=True)

            callback = server.get_callback("update_schedule")
            if callback:
                result = callback(callback_data)
                return jsonify(
                    {"success": result.get("success", True), "data": result}
                )
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов обновления расписания не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка обновления расписания: {e}")
            return _internal_error_response()

    @app.route("/api/schedule/<task_id>/toggle", methods=["POST"])
    @rate_limit
    @require_api_key
    def toggle_schedule(task_id: str):
        """
        Включение или отключение запланированной задачи.

        Args:
            task_id: ID задачи для переключения

        Тело запроса (JSON):
            - enabled: bool

        Returns:
            JSON с новым состоянием включения
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
            try:
                validated = ToggleScheduleRequest(**data)
            except ValidationError as e:
                return handle_validation_error(e)

            callback = server.get_callback("toggle_schedule")
            if callback:
                result = callback(task_id, validated.enabled)
                return jsonify({"success": True, "data": result})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов переключения расписания не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка переключения расписания: {e}")
            return _internal_error_response()

    @app.route("/api/devices", methods=["GET"])
    @require_api_key
    def get_devices():
        """
        Получение доступных аудиоустройств.

        Returns:
            JSON со списком устройств ввода/вывода
        """
        try:
            callback = server.get_callback("devices")
            if callback:
                devices = callback()
                return jsonify({"success": True, "data": devices})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов устройств не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка получения устройств: {e}")
            return _internal_error_response()

    @app.route("/api/windows", methods=["GET"])
    @require_api_key
    def get_windows():
        """
        Получение доступных окон для захвата.

        Returns:
            JSON со списком окон
        """
        try:
            callback = server.get_callback("windows")
            if callback:
                windows = callback()
                return jsonify({"success": True, "data": windows})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов окон не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка получения окон: {e}")
            return _internal_error_response()

    @app.route("/api/config", methods=["GET"])
    @require_api_key
    def get_config():
        """
        Получение текущей конфигурации.

        Returns:
            JSON с конфигурацией
        """
        try:
            callback = server.get_callback("get_config")
            if callback:
                config = callback()
                return jsonify({"success": True, "data": config})
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов конфигурации не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка получения конфигурации: {e}")
            return _internal_error_response()

    @app.route("/api/config", methods=["PUT"])
    @rate_limit
    @require_api_key
    def update_config():
        """
        Обновление конфигурации.

        Тело запроса (JSON):
            Поля конфигурации для обновления

        Returns:
            JSON с результатом
        """
        try:
            data = request.get_json() or {}

            # Валидация входных данных
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
            return jsonify(
                {
                    "success": False,
                    "error": "Обратный вызов обновления конфигурации не установлен",
                }
            ), 500

        except Exception as e:
            logger.exception(f"Ошибка обновления конфигурации: {e}")
            return _internal_error_response()

    @app.route("/health", methods=["GET"])
    def health_check():
        """Эндпоинт проверки здоровья."""
        return jsonify(
            {"status": "ok", "timestamp": datetime.now().isoformat()}
        )

    logger.info("Маршруты API зарегистрированы")
