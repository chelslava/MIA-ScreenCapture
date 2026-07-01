"""
Модуль API сервера
==================

REST API сервер на базе Flask для удалённого управления рекордером.
Работает в отдельном потоке, чтобы не блокировать GUI.
"""
# mypy: disable-error-code=import-untyped

import logging
import os
import shutil
import socket
import threading
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify
from flask_cors import CORS
from waitress.server import create_server
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from api.auth import API_KEY_CONFIG_KEY
from api.error_mapping import map_exception_to_api_error
from api.idempotency_store import APIIdempotencyStore
from api.observability import APIServerObservability
from api.operation_store import APIOperationStore
from api.request_lifecycle import register_request_lifecycle
from api.runtime_models import APIOperation, IdempotencyBeginResult
from logger_config import get_module_logger
from version import get_version

logger = get_module_logger(__name__)

_REQUEST_ID_HEADER = "X-Request-ID"
_SERVER_STOP_WAIT_SECONDS = 10.0
_MAX_REQUEST_BODY_BYTES = 1024 * 1024
_CORS_ALLOWED_ORIGIN_REGEX = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
_CORS_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
_CORS_ALLOWED_HEADERS = [
    "Authorization",
    "Content-Type",
    "Idempotency-Key",
    "X-API-Key",
    _REQUEST_ID_HEADER,
]
_HIGH_FREQUENCY_PATH_PREFIXES = (
    "/health",
    "/api/v1/status",
    "/api/status",
    "/api/v1/events",
    "/api/v1/observability",
)

_HEALTH_DISK_CRITICAL_MB = 100
_HEALTH_DISK_DEGRADED_MB = 1024
_HEALTH_RATE_LIMIT_SECONDS = 1.0
_WAITRESS_SHUTDOWN_PATCH_LOCK = threading.Lock()
_WAITRESS_SHUTDOWN_PATCHED = False


def _patch_waitress_shutdown_for_windows() -> None:
    """
    Применяет workaround для shutdown waitress на Windows.

    При гонке закрытия trigger-сокета waitress может выбрасывать
    ``OSError: [WinError 10038]`` во внутренних worker-потоках.
    Ошибка не влияет на обработку запросов, но засоряет лог.
    """
    global _WAITRESS_SHUTDOWN_PATCHED

    if os.name != "nt":
        return

    with _WAITRESS_SHUTDOWN_PATCH_LOCK:
        if _WAITRESS_SHUTDOWN_PATCHED:
            return

        try:
            from waitress import trigger as waitress_trigger
        except ImportError as e:
            logger.debug(
                "Не удалось применить workaround shutdown waitress: %s",
                e,
            )
            return

        original_pull = waitress_trigger.trigger._physical_pull

        def _safe_physical_pull(self: Any) -> None:
            try:
                original_pull(self)
            except OSError as e:
                win_error = getattr(e, "winerror", None)
                if win_error == 10038 and getattr(self, "_closed", False):
                    return
                raise

        waitress_trigger.trigger._physical_pull = _safe_physical_pull
        _WAITRESS_SHUTDOWN_PATCHED = True
        logger.debug("Применён Windows workaround для shutdown waitress.")


class APIServer:
    """
    REST API сервер для управления рекордером.

    Предоставляет эндпоинты для:
    - Запуска/остановки/паузы записей
    - Получения статуса и списка записей
    - Управления запланированными задачами
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 5000,
        server_threads: int = 4,
        api_key: str | None = None,
        trust_proxy_headers: bool = False,
    ):
        """
        Инициализация API сервера.

        Args:
            host: Адрес хоста для привязки
            port: Номер порта для прослушивания
            server_threads: Количество потоков waitress
            api_key: Токен API для аутентификации
            trust_proxy_headers: Доверять X-Forwarded-For/X-Real-IP при
                определении IP клиента для rate limiting (включать только
                за доверенным reverse-proxy, см. #74)

        Raises:
            Не выбрасывает собственных исключений — создание Flask
            приложения (`_create_app()`) не оборачивается в try/except,
            поэтому ошибка инициализации Flask/CORS/auth (нетипичный
            случай) распространится вызывающему как есть.
        """
        self.host = host
        self.port = port
        self.server_threads = max(1, int(server_threads))
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        self.trust_proxy_headers = trust_proxy_headers
        _patch_waitress_shutdown_for_windows()

        # Flask приложение
        self.app: Flask | None = None
        self._server_thread: threading.Thread | None = None
        self._wsgi_server: Any | None = None
        self._running = False
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._version = get_version()
        self._operations = APIOperationStore()
        self._idempotency = APIIdempotencyStore()
        self._observability = APIServerObservability(
            idempotency_store=self._idempotency
        )

        # Обратные вызовы
        self._callbacks: dict[str, Callable] = {}
        self._websocket_manager: Any | None = None
        self._ws_transport: Any = None
        # time.monotonic(), не time.time() — см. check_health_rate_limit().
        self._health_last_request_time: float = 0.0
        self._health_lock = threading.Lock()

        # Создание Flask приложения
        self._create_app()

    def _create_app(self) -> None:
        from api.auth import init_api_auth
        from api.auth_rate_limiter import AuthRateLimitConfig, AuthRateLimiter
        from api.rate_limiter import RateLimitConfig
        from api.rate_limiter_persistence import (
            PersistentRateLimiter,
            RateLimiterStatePersistence,
        )

        state_persistence = RateLimiterStatePersistence()
        self._rate_limiter = PersistentRateLimiter(
            config=RateLimitConfig(trust_proxy_headers=self.trust_proxy_headers),
            persistence=state_persistence,
        )

        self._auth_rate_limiter = AuthRateLimiter(
            config=AuthRateLimitConfig(max_attempts=5, base_delay=60)
        )

        self._rate_limiter.load_state_on_init()

        self.app = Flask(__name__)
        CORS(
            self.app,
            origins=[_CORS_ALLOWED_ORIGIN_REGEX],
            methods=_CORS_ALLOWED_METHODS,
            allow_headers=_CORS_ALLOWED_HEADERS,
            expose_headers=[_REQUEST_ID_HEADER],
            supports_credentials=False,
            vary_header=True,
        )
        self.app.config["MAX_CONTENT_LENGTH"] = _MAX_REQUEST_BODY_BYTES

        # Инициализация API аутентификации
        self.api_key = init_api_auth(self.app, self.api_key)

        # Логирование API ключа для пользователя (частично, для безопасности)
        api_key = self.get_api_key()
        if api_key:
            # Показываем только начало и конец ключа для идентификации
            masked_key = (
                f"{api_key[:8]}...{api_key[-4:]}"
                if len(api_key) > 12
                else "***"
            )
            logger.info(f"API ключ: {masked_key}")
            logger.warning(
                "Сохраните этот ключ для использования с CLI! "
                "Установите переменную окружения MIA_API_KEY для постоянного ключа."
            )

        # Регистрация обработчиков ошибок
        @self.app.errorhandler(404)
        def not_found(e):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "not_found",
                            "message": "Не найдено",
                            "details": None,
                        },
                    }
                ),
                404,
            )

        @self.app.errorhandler(500)
        def server_error(e):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "internal_error",
                            "message": "Внутренняя ошибка сервера",
                            "details": None,
                        },
                    }
                ),
                500,
            )

        @self.app.errorhandler(BadRequest)
        def bad_request(e):
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "bad_request",
                            "message": "Некорректный JSON в теле запроса",
                            "details": None,
                        },
                    }
                ),
                400,
            )

        @self.app.errorhandler(RequestEntityTooLarge)
        def payload_too_large(e):
            assert self.app is not None
            max_size = int(self.app.config.get("MAX_CONTENT_LENGTH", 0))
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": "payload_too_large",
                            "message": (
                                "Слишком большой запрос. "
                                f"Максимальный размер: {max_size} байт"
                            ),
                            "details": None,
                        },
                    }
                ),
                413,
            )

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.exception(f"Ошибка API: {e}")
            mapped = map_exception_to_api_error(e)
            return (
                jsonify(
                    {
                        "success": False,
                        "error": {
                            "code": mapped.code,
                            "message": mapped.message,
                            "details": mapped.details,
                        },
                    }
                ),
                mapped.status_code,
            )

        register_request_lifecycle(
            self.app,
            request_id_header=_REQUEST_ID_HEADER,
            observability=self._observability,
            health_payload_factory=self._get_health_payload,
            access_log_level_resolver=self._resolve_access_log_level,
        )

        self._init_websocket_transport()

        logger.info("Flask приложение создано")

    def _init_websocket_transport(self) -> None:
        """Инициализация WebSocket транспорта."""
        if self.app is None:
            return

        try:
            from flask_sock import Sock

            from api.websocket_transport import (
                WebSocketTransport,
                create_websocket_handler,
            )

            sock = Sock(self.app)

            self._ws_transport = WebSocketTransport(
                websocket_manager=self._websocket_manager,
                auth_check=self._check_ws_auth,
            )

            sock.route("/ws")(create_websocket_handler(self._ws_transport))
            logger.info("WebSocket transport инициализирован на /ws")

        except ImportError as e:
            logger.warning(
                "Flask-Sock не установлен, WebSocket transport недоступен: %s",
                e,
            )
            self._ws_transport = None

    def _check_ws_auth(self, token: str) -> bool:
        """Проверка токена для WebSocket подключения."""
        api_key = self.get_api_key()
        if not api_key:
            return True
        return token == api_key

    @staticmethod
    def _resolve_access_log_level(path: str, status_code: int) -> int:
        """Определяет уровень access-лога для снижения I/O overhead."""
        if status_code >= 500:
            return logging.ERROR
        if status_code >= 400:
            return logging.WARNING

        normalized_path = path or ""
        if normalized_path.startswith(_HIGH_FREQUENCY_PATH_PREFIXES):
            return logging.DEBUG
        return logging.INFO

    def set_callback(self, action: str, callback: Callable) -> None:
        """
        Установка функции обратного вызова для действия.

        Args:
            action: Имя действия (start, stop, pause, status и т.д.)
            callback: Функция обратного вызова

        Raises:
            Не выбрасывает исключений — простая запись в словарь.
        """
        self._callbacks[action] = callback

    def get_callback(self, action: str) -> Callable | None:
        """
        Получение обратного вызова для действия.

        Args:
            action: Имя действия

        Returns:
            Функция обратного вызова или None

        Raises:
            Не выбрасывает исключений — `dict.get()` с явным None по умолчанию.
        """
        return self._callbacks.get(action)

    def set_websocket_manager(self, manager: Any) -> None:
        """
        Устанавливает менеджер событий для real-time уведомлений.

        Raises:
            Не выбрасывает исключений — простое присваивание атрибута.
        """
        self._websocket_manager = manager

    def get_websocket_manager(self) -> Any | None:
        """
        Возвращает менеджер real-time уведомлений.

        Raises:
            Не выбрасывает исключений.
        """
        return self._websocket_manager

    def submit_background_operation(
        self,
        operation_type: str,
        runner: Callable[[], Any],
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> APIOperation:
        """
        Запускает фоновую операцию API.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIOperationStore.submit_typed()`; исключение из `runner`
            выполняется в фоновом потоке и не распространяется в вызывающий
            код этого метода (см. `APIOperation`/`get_background_operation`
            для получения результата/ошибки).
        """
        return self._operations.submit_typed(
            operation_type,
            runner,
            request_id=request_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )

    def get_background_operation(
        self,
        operation_id: str,
    ) -> APIOperation | None:
        """
        Возвращает состояние фоновой операции.

        Raises:
            Не выбрасывает исключений — неизвестный `operation_id`
            приводит к `None`, а не к исключению.
        """
        return self._operations.get_typed(operation_id)

    def wait_for_background_operation(
        self,
        operation_id: str,
        timeout: float,
    ) -> APIOperation | None:
        """
        Ожидает завершения фоновой операции.

        Raises:
            Не выбрасывает исключений — истечение `timeout` или неизвестный
            `operation_id` сообщаются через возвращаемое значение, а не
            исключение (`TimeoutError` не используется).
        """
        return self._operations.wait_typed(operation_id, timeout)

    def begin_idempotency_request(
        self,
        key: str,
        fingerprint: str,
    ) -> IdempotencyBeginResult:
        """
        Начинает идемпотентный запрос или возвращает cached-результат.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIIdempotencyStore.begin()`.
        """
        return self._idempotency.begin(key, fingerprint)

    def complete_idempotency_request(
        self,
        key: str,
        status_code: int,
        body_bytes: bytes,
        mimetype: str | None,
    ) -> None:
        """
        Сохраняет результат идемпотентного запроса в TTL-хранилище.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIIdempotencyStore.complete()`.
        """
        self._idempotency.complete(
            key=key,
            status_code=status_code,
            body_bytes=body_bytes,
            mimetype=mimetype,
        )

    def abort_idempotency_request(self, key: str) -> None:
        """
        Удаляет in-progress запись идемпотентного запроса.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIIdempotencyStore.abort()`.
        """
        self._idempotency.abort(key)

    def start(self) -> bool:
        """
        Запуск API сервера в фоновом потоке.

        Returns:
            True если сервер успешно запущен

        Raises:
            Не выбрасывает исключений: `OSError`/`RuntimeError` от
            `_validate_bind_address()` (например, порт уже занят)
            перехватываются внутри, ошибка сообщается через возвращаемое
            значение `False`.
        """
        with self._lock:
            if self._running:
                logger.warning("API сервер уже запущен")
                return False

            if not self._idempotency.is_running():
                self._idempotency = APIIdempotencyStore()
            if not self._operations.is_running():
                self._operations = APIOperationStore()

            if self._ws_transport:
                self._ws_transport.start()

            try:
                self._validate_bind_address()
                self._running = True
                self._server_thread = threading.Thread(
                    target=self._run_server, daemon=True
                )
                self._server_thread.start()

                logger.info(f"API сервер запущен на {self.host}:{self.port}")
                return True

            except (OSError, RuntimeError) as e:
                logger.error(f"Не удалось запустить API сервер: {e}")
                self._running = False
                return False

    def _validate_bind_address(self) -> None:
        """Проверяет возможность bind host/port до запуска waitress."""
        address_candidates = socket.getaddrinfo(
            self.host,
            self.port,
            type=socket.SOCK_STREAM,
        )
        last_error: OSError | None = None

        for family, socktype, proto, _, sockaddr in address_candidates:
            test_socket = socket.socket(family, socktype, proto)
            try:
                test_socket.bind(sockaddr)
                return
            except OSError as e:
                last_error = e
            finally:
                test_socket.close()

        if last_error is not None:
            raise OSError(
                f"Невозможно запустить API на {self.host}:{self.port}: "
                f"{last_error}"
            ) from last_error

    def _run_server(self) -> None:
        """Запуск WSGI сервера."""
        try:
            # Создаём управляемый waitress сервер, который начинает
            # принимать соединения сразу после запуска run().
            self._wsgi_server = create_server(
                self.app,
                host=self.host,
                port=self.port,
                threads=self.server_threads,
                clear_untrusted_proxy_headers=True,
            )
            self._wsgi_server.run()
        except (OSError, RuntimeError) as e:
            logger.error(f"Ошибка сервера: {e}")
        finally:
            self._running = False
            self._wsgi_server = None

    def stop(self) -> None:
        """
        Остановка API сервера.

        Raises:
            Не выбрасывает исключений: ошибка закрытия waitress-сервера
            (`OSError`/`RuntimeError`) перехватывается внутри и только
            логируется.
        """
        server_thread: threading.Thread | None
        wsgi_server: Any | None
        with self._lock:
            self._running = False
            server_thread = self._server_thread
            wsgi_server = self._wsgi_server

        if self._ws_transport:
            self._ws_transport.stop()

        if wsgi_server is not None:
            try:
                wsgi_server.close()
            except (OSError, RuntimeError) as e:
                logger.warning(f"Ошибка закрытия API сервера: {e}")

        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=_SERVER_STOP_WAIT_SECONDS)
            if server_thread.is_alive():
                logger.warning(
                    "Поток API сервера не завершился за %.1f секунд",
                    _SERVER_STOP_WAIT_SECONDS,
                )

        self._idempotency.stop()
        self._operations.stop()
        logger.info("API сервер остановлен")

    def is_running(self) -> bool:
        """
        Проверка работы сервера.

        Raises:
            Не выбрасывает исключений.
        """
        return self._running

    def get_url(self) -> str:
        """
        Получение URL сервера.

        Raises:
            Не выбрасывает исключений.
        """
        return f"http://{self.host}:{self.port}"

    def get_status(self) -> dict[str, Any]:
        """
        Получение статуса API сервера.

        Returns:
            Словарь со статусом, адресом и информацией об аутентификации.

        Raises:
            Не выбрасывает исключений.
        """
        return {
            "running": self._running,
            "host": self.host,
            "port": self.port,
            "url": self.get_url(),
            "api_key": self.get_api_key(),
            "api_key_set": bool(self.get_api_key()),
        }

    def set_api_key(self, api_key: str | None) -> None:
        """
        Обновление API ключа в памяти и активном Flask приложении.

        Args:
            api_key: Новый API ключ или None.

        Raises:
            Не выбрасывает исключений.
        """
        normalized_key = (
            api_key.strip() if api_key and api_key.strip() else None
        )
        self.api_key = normalized_key

        if self.app is not None:
            if normalized_key is not None:
                self.app.config[API_KEY_CONFIG_KEY] = normalized_key
            else:
                self.app.config.pop(API_KEY_CONFIG_KEY, None)

    def get_api_key(self) -> str | None:
        """
        Получение текущего API ключа.

        Returns:
            API ключ или None если не установлен

        Raises:
            Не выбрасывает исключений.
        """
        from api.auth import get_api_key

        value = get_api_key(self.app)
        return value if isinstance(value, str) else None

    def get_runtime_api_key(self) -> str | None:
        """
        Получение реального (не маскированного) API ключа runtime.

        Returns:
            Исходный API ключ или None если не установлен.

        Raises:
            Не выбрасывает исключений.
        """
        if self.app is not None:
            value = self.app.config.get(API_KEY_CONFIG_KEY)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(self.api_key, str) and self.api_key.strip():
            return self.api_key.strip()
        return None

    def _check_ffmpeg(self) -> dict[str, Any]:
        """Проверяет доступность FFmpeg."""
        from recorder.utils import check_ffmpeg

        status = check_ffmpeg()
        result: dict[str, Any] = {
            "status": "ok" if status.available else "error"
        }
        if status.version:
            result["version"] = status.version
        if status.path:
            result["path"] = status.path
        if status.error:
            result["error"] = status.error
        if status.recommendation:
            result["recommendation"] = status.recommendation
        return result

    def _check_disk(self) -> dict[str, Any]:
        """Проверяет свободное место на диске."""
        try:
            usage = shutil.disk_usage(Path.home())
            free_gb = round(usage.free / (1024**3), 2)
            free_mb = usage.free / (1024 * 1024)
            if free_mb < _HEALTH_DISK_CRITICAL_MB:
                disk_status = "critical"
            elif free_mb < _HEALTH_DISK_DEGRADED_MB:
                disk_status = "degraded"
            else:
                disk_status = "ok"
            return {"status": disk_status, "free_gb": free_gb}
        except OSError as e:
            return {"status": "error", "error": str(e)}

    def _check_recording(self) -> dict[str, Any]:
        """Возвращает состояние записи через callback."""
        callback = self._callbacks.get("status")
        if callback is None:
            return {"status": "idle"}
        try:
            data = callback()
            if not isinstance(data, dict):
                return {"status": "idle"}
            if data.get("is_recording"):
                rec_status = "paused" if data.get("is_paused") else "active"
            else:
                rec_status = "idle"
            return {"status": rec_status}
        except Exception:
            return {"status": "idle"}

    def check_health_rate_limit(self) -> bool:
        """
        Возвращает True если запрос разрешён, False если нужно вернуть 429.

        Использует time.monotonic(), а не time.time(): измерение
        интервала между запросами не должно зависеть от коррекции
        системных часов (NTP), как и в общем InMemoryRateLimiter
        (api/rate_limiter.py).

        Raises:
            Не выбрасывает исключений.
        """
        now = time.monotonic()
        with self._health_lock:
            if (
                now - self._health_last_request_time
                < _HEALTH_RATE_LIMIT_SECONDS
            ):
                return False
            self._health_last_request_time = now
            return True

    def _get_health_payload(self) -> dict[str, Any]:
        """Возвращает расширенный health payload с проверками компонентов."""
        websocket = (
            self._websocket_manager.get_stats()
            if self._websocket_manager is not None
            else {"transport_ready": False}
        )

        ffmpeg_check = self._check_ffmpeg()
        disk_check = self._check_disk()
        recording_check = self._check_recording()

        # Определяем итоговый статус
        disk_status = disk_check.get("status", "ok")
        if disk_status == "critical":
            overall_status = "unhealthy"
        elif (
            disk_status in ("degraded", "error")
            or ffmpeg_check.get("status") == "error"
        ):
            overall_status = "degraded"
        else:
            overall_status = "ok"

        return {
            "status": overall_status,
            "timestamp": datetime.now(UTC).isoformat(),
            "version": self._version,
            "uptime_seconds": round(time.monotonic() - self._start_time, 3),
            "websocket": websocket,
            "checks": {
                "ffmpeg": ffmpeg_check,
                "disk": disk_check,
                "recording": recording_check,
            },
        }

    def get_observability_metrics(self) -> dict[str, Any]:
        """
        Возвращает снапшот эксплуатационных метрик API.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIServerObservability.get_metrics_snapshot()`,
            `APIIdempotencyStore.get_size()` и
            `APIOperationStore.get_metrics_snapshot()`.
        """
        payload = self._observability.get_metrics_snapshot()
        payload["idempotency_store_size"] = self._idempotency.get_size()
        payload["background_operations"] = (
            self._operations.get_metrics_snapshot()
        )
        return payload

    def get_observability_baseline(self) -> dict[str, Any]:
        """
        Возвращает baseline SLO по текущим эксплуатационным метрикам.

        Raises:
            Не выбрасывает собственных исключений напрямую — делегирует в
            `APIServerObservability.get_baseline()`.
        """
        return self._observability.get_baseline()
