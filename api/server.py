"""
Модуль API сервера
==================

REST API сервер на базе Flask для удалённого управления рекордером.
Работает в отдельном потоке, чтобы не блокировать GUI.
"""

import logging
import re
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
from flask import Flask, g, jsonify, request
from flask_cors import CORS
from waitress.server import create_server

from api.auth import API_KEY_CONFIG_KEY
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_VERSION_FALLBACK = "unknown"
_REQUEST_ID_HEADER = "X-Request-ID"
_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
_OPERATION_RESULT_TTL_SECONDS = 600.0
_SERVER_STOP_WAIT_SECONDS = 10.0
_HIGH_FREQUENCY_PATH_PREFIXES = (
    "/health",
    "/api/v1/status",
    "/api/status",
    "/api/v1/events",
    "/api/v1/observability",
)


class APIOperationStore:
    """Потокобезопасное хранилище фоновых операций API."""

    def __init__(self, ttl_seconds: float = _OPERATION_RESULT_TTL_SECONDS):
        self._ttl_seconds = ttl_seconds
        self._lock = threading.Lock()
        self._operations: dict[str, dict[str, Any]] = {}
        self._events: dict[str, threading.Event] = {}

    def submit(
        self,
        operation_type: str,
        runner: Callable[[], Any],
    ) -> dict[str, Any]:
        """Запускает фоновую операцию и возвращает её snapshot."""
        operation_id = uuid.uuid4().hex
        now_iso = datetime.now(UTC).isoformat()
        operation = {
            "id": operation_id,
            "type": operation_type,
            "status": "running",
            "created_at": now_iso,
            "updated_at": now_iso,
            "completed_at": None,
            "result": None,
            "error": None,
        }
        done_event = threading.Event()

        with self._lock:
            self._cleanup_expired_locked()
            self._operations[operation_id] = operation
            self._events[operation_id] = done_event

        thread = threading.Thread(
            target=self._run_operation,
            args=(operation_id, runner),
            daemon=True,
            name=f"api-op-{operation_type}",
        )
        thread.start()
        return self.get(operation_id) or operation

    def _run_operation(
        self,
        operation_id: str,
        runner: Callable[[], Any],
    ) -> None:
        """Выполняет операцию и сохраняет результат."""
        try:
            result = runner()
            self._complete(operation_id, status="succeeded", result=result)
        except Exception as e:
            self._complete(operation_id, status="failed", error=str(e))

    def _complete(
        self,
        operation_id: str,
        status: str,
        result: Any | None = None,
        error: str | None = None,
    ) -> None:
        now_iso = datetime.now(UTC).isoformat()
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                return
            operation["status"] = status
            operation["updated_at"] = now_iso
            operation["completed_at"] = now_iso
            operation["result"] = result
            operation["error"] = error
            done_event = self._events.get(operation_id)
            if done_event is not None:
                done_event.set()

    def get(self, operation_id: str) -> dict[str, Any] | None:
        """Возвращает snapshot операции по id."""
        with self._lock:
            self._cleanup_expired_locked()
            operation = self._operations.get(operation_id)
            if operation is None:
                return None
            return dict(operation)

    def wait(
        self,
        operation_id: str,
        timeout: float,
    ) -> dict[str, Any] | None:
        """Ожидает завершение операции ограниченное время."""
        with self._lock:
            event = self._events.get(operation_id)
        if event is None:
            return self.get(operation_id)
        event.wait(timeout=timeout)
        return self.get(operation_id)

    def _cleanup_expired_locked(self) -> None:
        now = datetime.now(UTC).timestamp()
        stale_ids: list[str] = []
        for op_id, op in self._operations.items():
            completed_at = op.get("completed_at")
            if completed_at is None:
                continue
            try:
                completed_dt = datetime.fromisoformat(completed_at)
                age = now - completed_dt.timestamp()
            except Exception:
                age = self._ttl_seconds + 1
            if age > self._ttl_seconds:
                stale_ids.append(op_id)

        for op_id in stale_ids:
            self._operations.pop(op_id, None)
            self._events.pop(op_id, None)


class APIServerObservability:
    """Потокобезопасный сбор базовых эксплуатационных метрик API."""

    def __init__(self, max_latency_samples: int = 2000) -> None:
        self._lock = threading.Lock()
        self._started_at = time.monotonic()
        self._requests_total = 0
        self._requests_inflight = 0
        self._errors_total = 0
        self._status_counts: dict[str, int] = {}
        self._method_counts: dict[str, int] = {}
        self._path_counts: dict[str, int] = {}
        self._latency_ms: deque[float] = deque(maxlen=max_latency_samples)
        self._process = psutil.Process()

    def request_started(self) -> None:
        with self._lock:
            self._requests_inflight += 1

    def request_finished(
        self,
        method: str,
        path: str,
        status_code: int,
        latency_seconds: float,
    ) -> None:
        status_key = str(status_code)
        latency_ms = max(0.0, latency_seconds * 1000.0)
        with self._lock:
            self._requests_total += 1
            self._requests_inflight = max(0, self._requests_inflight - 1)
            if status_code >= 500:
                self._errors_total += 1
            self._status_counts[status_key] = (
                self._status_counts.get(status_key, 0) + 1
            )
            self._method_counts[method] = (
                self._method_counts.get(method, 0) + 1
            )
            self._path_counts[path] = self._path_counts.get(path, 0) + 1
            self._latency_ms.append(latency_ms)

    @staticmethod
    def _percentile(sorted_values: list[float], percentile: float) -> float:
        if not sorted_values:
            return 0.0
        if percentile <= 0:
            return sorted_values[0]
        if percentile >= 100:
            return sorted_values[-1]
        index = (len(sorted_values) - 1) * (percentile / 100.0)
        lower = int(index)
        upper = min(lower + 1, len(sorted_values) - 1)
        weight = index - lower
        return (
            sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight
        )

    def _latency_stats(self) -> dict[str, float | int]:
        samples = sorted(self._latency_ms)
        if not samples:
            return {
                "count": 0,
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "max_ms": 0.0,
            }
        return {
            "count": len(samples),
            "avg_ms": round(sum(samples) / len(samples), 3),
            "p50_ms": round(self._percentile(samples, 50), 3),
            "p95_ms": round(self._percentile(samples, 95), 3),
            "p99_ms": round(self._percentile(samples, 99), 3),
            "max_ms": round(samples[-1], 3),
        }

    def _resource_stats(self) -> dict[str, float | int]:
        memory_info = self._process.memory_info()
        return {
            "rss_mb": round(memory_info.rss / (1024 * 1024), 3),
            "threads": self._process.num_threads(),
            "cpu_percent": round(self._process.cpu_percent(interval=None), 3),
        }

    def get_metrics_snapshot(self) -> dict[str, Any]:
        with self._lock:
            requests_total = self._requests_total
            requests_inflight = self._requests_inflight
            errors_total = self._errors_total
            status_counts = dict(self._status_counts)
            method_counts = dict(self._method_counts)
            path_counts = dict(self._path_counts)
            uptime = max(0.0, time.monotonic() - self._started_at)

        top_paths = sorted(
            path_counts.items(), key=lambda item: item[1], reverse=True
        )[:10]
        latency = self._latency_stats()
        resources = self._resource_stats()
        requests_per_second = (
            round(requests_total / uptime, 6) if uptime else 0.0
        )
        error_rate_percent = (
            round((errors_total / requests_total) * 100.0, 6)
            if requests_total
            else 0.0
        )

        return {
            "uptime_seconds": round(uptime, 3),
            "requests_total": requests_total,
            "requests_inflight": requests_inflight,
            "requests_per_second": requests_per_second,
            "errors_total": errors_total,
            "error_rate_percent": error_rate_percent,
            "status_codes": status_counts,
            "methods": method_counts,
            "top_paths": [
                {"path": path, "count": count} for path, count in top_paths
            ],
            "latency_ms": latency,
            "resources": resources,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    def get_baseline(self) -> dict[str, Any]:
        snapshot = self.get_metrics_snapshot()
        latency = snapshot["latency_ms"]
        return {
            "generated_at": snapshot["generated_at"],
            "uptime_seconds": snapshot["uptime_seconds"],
            "sample_size": latency["count"],
            "slo_targets": {
                "p95_latency_ms": 100.0,
                "error_rate_percent": 1.0,
            },
            "current": {
                "p95_latency_ms": latency["p95_ms"],
                "error_rate_percent": snapshot["error_rate_percent"],
                "requests_per_second": snapshot["requests_per_second"],
                "rss_mb": snapshot["resources"]["rss_mb"],
            },
            "meets_targets": {
                "latency": latency["p95_ms"] <= 100.0,
                "error_rate": snapshot["error_rate_percent"] <= 1.0,
            },
        }


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
        api_key: str | None = None,
    ):
        """
        Инициализация API сервера.

        Args:
            host: Адрес хоста для привязки
            port: Номер порта для прослушивания
            api_key: Токен API для аутентификации
        """
        self.host = host
        self.port = port
        self.api_key = api_key.strip() if api_key and api_key.strip() else None

        # Flask приложение
        self.app: Flask | None = None
        self._server_thread: threading.Thread | None = None
        self._wsgi_server: Any | None = None
        self._running = False
        self._lock = threading.Lock()
        self._start_time = time.monotonic()
        self._version = self._load_version()
        self._observability = APIServerObservability()
        self._operations = APIOperationStore()

        # Обратные вызовы
        self._callbacks: dict[str, Callable] = {}
        self._websocket_manager: Any | None = None

        # Создание Flask приложения
        self._create_app()

    def _create_app(self) -> None:
        """Создание и настройка Flask приложения."""
        from api.auth import init_api_auth
        from api.rate_limiter import init_rate_limiter

        self.app = Flask(__name__)
        CORS(self.app)

        # Инициализация API аутентификации
        self.api_key = init_api_auth(self.app, self.api_key)
        # Инициализация rate limiter (применяется декораторами в routes.py)
        init_rate_limiter(self.app)

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
            return jsonify({"error": "Не найдено"}), 404

        @self.app.errorhandler(500)
        def server_error(e):
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

        @self.app.errorhandler(Exception)
        def handle_exception(e):
            logger.exception(f"Ошибка API: {e}")
            return jsonify({"error": "Внутренняя ошибка сервера"}), 500

        @self.app.before_request
        def assign_request_id() -> None:
            request_id = request.headers.get(_REQUEST_ID_HEADER, "").strip()
            if not request_id:
                request_id = uuid.uuid4().hex
            g.request_id = request_id
            g.request_started_at = time.monotonic()
            self._observability.request_started()

            if request.path == "/health":
                return jsonify(self._get_health_payload())  # type: ignore[return-value]

        @self.app.after_request
        def add_request_id_header(response):
            request_id = getattr(g, "request_id", None)
            if not request_id:
                request_id = uuid.uuid4().hex
                g.request_id = request_id
            response.headers[_REQUEST_ID_HEADER] = request_id
            started_at = getattr(g, "request_started_at", None)
            latency_ms = 0.0
            if isinstance(started_at, float):
                latency_seconds = max(0.0, time.monotonic() - started_at)
                latency_ms = latency_seconds * 1000.0
                self._observability.request_finished(
                    method=request.method,
                    path=request.path,
                    status_code=response.status_code,
                    latency_seconds=latency_seconds,
                )
            logger.log(
                self._resolve_access_log_level(
                    path=request.path,
                    status_code=response.status_code,
                ),
                "API %s %s -> %s (%.2f ms) request_id=%s ip=%s",
                request.method,
                request.path,
                response.status_code,
                latency_ms,
                request_id,
                request.remote_addr,
            )
            return response

        logger.info("Flask приложение создано")

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
        """
        self._callbacks[action] = callback

    def get_callback(self, action: str) -> Callable | None:
        """
        Получение обратного вызова для действия.

        Args:
            action: Имя действия

        Returns:
            Функция обратного вызова или None
        """
        return self._callbacks.get(action)

    def set_websocket_manager(self, manager: Any) -> None:
        """Устанавливает менеджер событий для real-time уведомлений."""
        self._websocket_manager = manager

    def get_websocket_manager(self) -> Any | None:
        """Возвращает менеджер real-time уведомлений."""
        return self._websocket_manager

    def submit_background_operation(
        self,
        operation_type: str,
        runner: Callable[[], Any],
    ) -> dict[str, Any]:
        """Запускает фоновую операцию API."""
        return self._operations.submit(operation_type, runner)

    def get_background_operation(
        self,
        operation_id: str,
    ) -> dict[str, Any] | None:
        """Возвращает состояние фоновой операции."""
        return self._operations.get(operation_id)

    def wait_for_background_operation(
        self,
        operation_id: str,
        timeout: float,
    ) -> dict[str, Any] | None:
        """Ожидает завершения фоновой операции."""
        return self._operations.wait(operation_id, timeout)

    def start(self) -> bool:
        """
        Запуск API сервера в фоновом потоке.

        Returns:
            True если сервер успешно запущен
        """
        with self._lock:
            if self._running:
                logger.warning("API сервер уже запущен")
                return False

            try:
                self._running = True
                self._server_thread = threading.Thread(
                    target=self._run_server, daemon=True
                )
                self._server_thread.start()

                logger.info(f"API сервер запущен на {self.host}:{self.port}")
                return True

            except Exception as e:
                logger.error(f"Не удалось запустить API сервер: {e}")
                self._running = False
                return False

    def _run_server(self) -> None:
        """Запуск WSGI сервера."""
        try:
            # Создаём управляемый waitress сервер, который начинает
            # принимать соединения сразу после запуска run().
            self._wsgi_server = create_server(
                self.app,
                host=self.host,
                port=self.port,
                threads=4,
                clear_untrusted_proxy_headers=True,
            )
            self._wsgi_server.run()
        except Exception as e:
            logger.error(f"Ошибка сервера: {e}")
        finally:
            self._running = False
            self._wsgi_server = None

    def stop(self) -> None:
        """Остановка API сервера."""
        server_thread: threading.Thread | None
        with self._lock:
            self._running = False
            server_thread = self._server_thread
            if self._wsgi_server is not None:
                try:
                    self._wsgi_server.close()
                except Exception as e:
                    logger.warning(f"Ошибка закрытия API сервера: {e}")

        if server_thread and server_thread.is_alive():
            server_thread.join(timeout=_SERVER_STOP_WAIT_SECONDS)
            if server_thread.is_alive():
                logger.warning(
                    "Поток API сервера не завершился за %.1f секунд",
                    _SERVER_STOP_WAIT_SECONDS,
                )

        logger.info("API сервер остановлен")

    def is_running(self) -> bool:
        """Проверка работы сервера."""
        return self._running

    def get_url(self) -> str:
        """Получение URL сервера."""
        return f"http://{self.host}:{self.port}"

    def get_status(self) -> dict[str, Any]:
        """
        Получение статуса API сервера.

        Returns:
            Словарь со статусом, адресом и информацией об аутентификации.
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
        """
        from api.auth import get_api_key

        return get_api_key(self.app)

    def _load_version(self) -> str:
        """Читает версию из pyproject.toml или возвращает fallback."""
        try:
            text = _PYPROJECT_PATH.read_text(encoding="utf-8")
            match = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
            if match:
                return match.group(1)
        except Exception as e:
            logger.debug(f"Не удалось прочитать версию из pyproject.toml: {e}")
        return _VERSION_FALLBACK

    def _get_health_payload(self) -> dict[str, Any]:
        """Возвращает расширенный health payload."""
        websocket = (
            self._websocket_manager.get_stats()
            if self._websocket_manager is not None
            else {"transport_ready": False}
        )
        return {
            "status": "ok",
            "timestamp": datetime.now(UTC).isoformat(),
            "version": self._version,
            "uptime_seconds": round(time.monotonic() - self._start_time, 3),
            "websocket": websocket,
        }

    def get_observability_metrics(self) -> dict[str, Any]:
        """Возвращает снапшот эксплуатационных метрик API."""
        return self._observability.get_metrics_snapshot()

    def get_observability_baseline(self) -> dict[str, Any]:
        """Возвращает baseline SLO по текущим эксплуатационным метрикам."""
        return self._observability.get_baseline()
