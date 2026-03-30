"""
Модуль API сервера
==================

REST API сервер на базе Flask для удалённого управления рекордером.
Работает в отдельном потоке, чтобы не блокировать GUI.
"""
# mypy: disable-error-code=import-untyped

import logging
import os
import re
import socket
import threading
import time
import uuid
from collections import deque
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psutil
from flask import Flask, jsonify
from flask_cors import CORS
from waitress.server import create_server
from werkzeug.exceptions import BadRequest, RequestEntityTooLarge

from api.auth import API_KEY_CONFIG_KEY
from api.error_mapping import map_exception_to_api_error
from api.request_lifecycle import register_request_lifecycle
from logger_config import get_module_logger

logger = get_module_logger(__name__)

_VERSION_FALLBACK = "unknown"
_REQUEST_ID_HEADER = "X-Request-ID"
_PYPROJECT_PATH = Path(__file__).resolve().parent.parent / "pyproject.toml"
_OPERATION_RESULT_TTL_SECONDS = 600.0
_IDEMPOTENCY_RESULT_TTL_SECONDS = 3600.0
_IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS = 30.0
_API_OPERATION_MAX_WORKERS = 2
_API_OPERATION_QUEUE_SIZE = 16
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
        except Exception as e:
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


class APIOperationStore:
    """Потокобезопасное хранилище фоновых операций API."""

    def __init__(
        self,
        ttl_seconds: float = _OPERATION_RESULT_TTL_SECONDS,
        max_workers: int = _API_OPERATION_MAX_WORKERS,
        max_queue_size: int = _API_OPERATION_QUEUE_SIZE,
    ):
        self._ttl_seconds = ttl_seconds
        self._max_workers = max(1, int(max_workers))
        self._max_queue_size = max(0, int(max_queue_size))
        self._max_inflight = self._max_workers + self._max_queue_size
        self._lock = threading.Lock()
        self._operations: dict[str, dict[str, Any]] = {}
        self._events: dict[str, threading.Event] = {}
        self._inflight_semaphore = threading.Semaphore(self._max_inflight)
        self._executor = ThreadPoolExecutor(
            max_workers=self._max_workers,
            thread_name_prefix="api-op-worker",
        )
        self._submitted_total = 0
        self._completed_total = 0
        self._failed_total = 0
        self._rejected_total = 0
        self._inflight_current = 0
        self._max_inflight_seen = 0
        self._stopped = False

    def submit(
        self,
        operation_type: str,
        runner: Callable[[], Any],
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Запускает фоновую операцию и возвращает её snapshot."""
        if self._stopped:
            return self._build_rejected_operation(
                operation_type,
                "Операции API недоступны: executor остановлен",
            )

        acquired = self._inflight_semaphore.acquire(blocking=False)
        if not acquired:
            return self._build_rejected_operation(
                operation_type,
                "Очередь фоновых операций API переполнена",
            )

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
            "request_id": request_id,
            "trace_id": trace_id,
            "client_ip": client_ip,
        }
        done_event = threading.Event()

        with self._lock:
            self._cleanup_expired_locked()
            self._operations[operation_id] = operation
            self._events[operation_id] = done_event
            self._submitted_total += 1
            self._inflight_current += 1
            self._max_inflight_seen = max(
                self._max_inflight_seen, self._inflight_current
            )

        try:
            self._executor.submit(self._run_operation, operation_id, runner)
        except Exception as e:
            self._release_inflight_slot()
            self._complete(
                operation_id,
                status="failed",
                error=f"Не удалось поставить операцию в очередь: {e}",
            )
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
        finally:
            self._release_inflight_slot()

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
            if status == "succeeded":
                self._completed_total += 1
            elif status == "failed":
                self._failed_total += 1
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

    def _build_rejected_operation(
        self,
        operation_type: str,
        error_message: str,
    ) -> dict[str, Any]:
        operation_id = uuid.uuid4().hex
        now_iso = datetime.now(UTC).isoformat()
        operation = {
            "id": operation_id,
            "type": operation_type,
            "status": "failed",
            "created_at": now_iso,
            "updated_at": now_iso,
            "completed_at": now_iso,
            "result": None,
            "error": error_message,
            "request_id": None,
            "trace_id": None,
            "client_ip": None,
        }
        with self._lock:
            self._cleanup_expired_locked()
            self._operations[operation_id] = operation
            done_event = threading.Event()
            done_event.set()
            self._events[operation_id] = done_event
            self._rejected_total += 1
            self._failed_total += 1
        return dict(operation)

    def _release_inflight_slot(self) -> None:
        with self._lock:
            if self._inflight_current > 0:
                self._inflight_current -= 1
        self._inflight_semaphore.release()

    def get_metrics_snapshot(self) -> dict[str, int | float]:
        """Возвращает метрики saturation bounded executor-а операций."""
        with self._lock:
            inflight = self._inflight_current
            queued = max(0, inflight - self._max_workers)
            saturation = (
                float(inflight) / float(self._max_inflight)
                if self._max_inflight > 0
                else 0.0
            )
            return {
                "workers": self._max_workers,
                "queue_capacity": self._max_queue_size,
                "max_inflight_capacity": self._max_inflight,
                "inflight": inflight,
                "queued": queued,
                "submitted_total": self._submitted_total,
                "completed_total": self._completed_total,
                "failed_total": self._failed_total,
                "rejected_total": self._rejected_total,
                "max_inflight_seen": self._max_inflight_seen,
                "saturation_ratio": round(saturation, 4),
            }

    def stop(self) -> None:
        """Останавливает executor фоновых операций."""
        with self._lock:
            self._stopped = True
        self._executor.shutdown(wait=False, cancel_futures=True)

    def is_running(self) -> bool:
        """Проверяет, что bounded executor ещё принимает задачи."""
        with self._lock:
            return not self._stopped


class APIIdempotencyStore:
    """Потокобезопасное TTL-хранилище результатов идемпотентных запросов."""

    def __init__(
        self,
        ttl_seconds: float = _IDEMPOTENCY_RESULT_TTL_SECONDS,
        cleanup_interval_seconds: float = _IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._cleanup_interval_seconds = cleanup_interval_seconds
        self._lock = threading.Lock()
        self._entries: dict[str, dict[str, Any]] = {}
        self._stop_event = threading.Event()
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_loop,
            name="api-idempotency-cleanup",
            daemon=True,
        )
        self._cleanup_thread.start()

    def begin(
        self,
        key: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        """Регистрирует начало операции или возвращает cached-результат."""
        now = time.monotonic()
        with self._lock:
            self._cleanup_expired_locked(now)
            entry = self._entries.get(key)
            if entry is None:
                self._entries[key] = {
                    "fingerprint": fingerprint,
                    "status": "running",
                    "created_at_monotonic": now,
                    "updated_at_monotonic": now,
                    "response": None,
                }
                return {"state": "started"}

            if entry["fingerprint"] != fingerprint:
                return {"state": "conflict"}

            if entry["status"] == "running":
                return {"state": "in_progress"}

            return {
                "state": "replay",
                "response": dict(entry["response"] or {}),
            }

    def complete(
        self,
        key: str,
        status_code: int,
        body_bytes: bytes,
        mimetype: str | None,
    ) -> None:
        """Фиксирует итоговый ответ запроса по idempotency key."""
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return
            if status_code >= 500:
                # 5xx не кешируем: клиент может безопасно повторить запрос.
                self._entries.pop(key, None)
                return
            entry["status"] = "completed"
            entry["updated_at_monotonic"] = now
            entry["response"] = {
                "status_code": status_code,
                "body_bytes": body_bytes,
                "mimetype": mimetype or "application/json",
            }

    def abort(self, key: str) -> None:
        """Откатывает in-progress запись после исключения."""
        with self._lock:
            self._entries.pop(key, None)

    def get_size(self) -> int:
        """Возвращает количество активных записей в idempotency store."""
        with self._lock:
            self._cleanup_expired_locked(time.monotonic())
            return len(self._entries)

    def stop(self) -> None:
        """Останавливает фоновой поток очистки."""
        self._stop_event.set()
        self._cleanup_thread.join(timeout=1.0)

    def is_running(self) -> bool:
        """Проверяет, активен ли поток очистки idempotency store."""
        return (
            self._cleanup_thread.is_alive() and not self._stop_event.is_set()
        )

    def _cleanup_loop(self) -> None:
        """Фоновая очистка устаревших записей idempotency store."""
        while not self._stop_event.wait(self._cleanup_interval_seconds):
            with self._lock:
                self._cleanup_expired_locked(time.monotonic())

    def _cleanup_expired_locked(self, now: float) -> None:
        stale_keys = [
            key
            for key, entry in self._entries.items()
            if (now - float(entry.get("updated_at_monotonic", now)))
            > self._ttl_seconds
        ]
        for key in stale_keys:
            self._entries.pop(key, None)


class APIServerObservability:
    """Потокобезопасный сбор базовых эксплуатационных метрик API."""

    _MAX_PATH_ENTRIES = 100

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
            # Ограничение роста path_counts
            if (
                len(self._path_counts) < self._MAX_PATH_ENTRIES
                or path in self._path_counts
            ):
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
        with self._lock:
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
        server_threads: int = 4,
        api_key: str | None = None,
    ):
        """
        Инициализация API сервера.

        Args:
            host: Адрес хоста для привязки
            port: Номер порта для прослушивания
            server_threads: Количество потоков waitress
            api_key: Токен API для аутентификации
        """
        self.host = host
        self.port = port
        self.server_threads = max(1, int(server_threads))
        self.api_key = api_key.strip() if api_key and api_key.strip() else None
        _patch_waitress_shutdown_for_windows()

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
        self._idempotency = APIIdempotencyStore()

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
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> dict[str, Any]:
        """Запускает фоновую операцию API."""
        return self._operations.submit(
            operation_type,
            runner,
            request_id=request_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )

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

    def begin_idempotency_request(
        self,
        key: str,
        fingerprint: str,
    ) -> dict[str, Any]:
        """Начинает идемпотентный запрос или возвращает cached-результат."""
        return self._idempotency.begin(key, fingerprint)

    def complete_idempotency_request(
        self,
        key: str,
        status_code: int,
        body_bytes: bytes,
        mimetype: str | None,
    ) -> None:
        """Сохраняет результат идемпотентного запроса в TTL-хранилище."""
        self._idempotency.complete(
            key=key,
            status_code=status_code,
            body_bytes=body_bytes,
            mimetype=mimetype,
        )

    def abort_idempotency_request(self, key: str) -> None:
        """Удаляет in-progress запись идемпотентного запроса."""
        self._idempotency.abort(key)

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

            if not self._idempotency.is_running():
                self._idempotency = APIIdempotencyStore()
            if not self._operations.is_running():
                self._operations = APIOperationStore()

            try:
                self._validate_bind_address()
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
        except Exception as e:
            logger.error(f"Ошибка сервера: {e}")
        finally:
            self._running = False
            self._wsgi_server = None

    def stop(self) -> None:
        """Остановка API сервера."""
        server_thread: threading.Thread | None
        wsgi_server: Any | None
        with self._lock:
            self._running = False
            server_thread = self._server_thread
            wsgi_server = self._wsgi_server

        if wsgi_server is not None:
            try:
                wsgi_server.close()
            except Exception as e:
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

        value = get_api_key(self.app)
        return value if isinstance(value, str) else None

    def get_runtime_api_key(self) -> str | None:
        """
        Получение реального (не маскированного) API ключа runtime.

        Returns:
            Исходный API ключ или None если не установлен.
        """
        if self.app is not None:
            value = self.app.config.get(API_KEY_CONFIG_KEY)
            if isinstance(value, str) and value.strip():
                return value.strip()
        if isinstance(self.api_key, str) and self.api_key.strip():
            return self.api_key.strip()
        return None

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
        payload = self._observability.get_metrics_snapshot()
        payload["idempotency_store_size"] = self._idempotency.get_size()
        payload["background_operations"] = (
            self._operations.get_metrics_snapshot()
        )
        return payload

    def get_observability_baseline(self) -> dict[str, Any]:
        """Возвращает baseline SLO по текущим эксплуатационным метрикам."""
        return self._observability.get_baseline()
