"""Хранилище фоновых операций API."""

from __future__ import annotations

import threading
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Any

from api.runtime_models import APIOperation, OperationStatus

_OPERATION_RESULT_TTL_SECONDS = 600.0
_API_OPERATION_MAX_WORKERS = 2
_API_OPERATION_QUEUE_SIZE = 16


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
        self._operations: dict[str, APIOperation] = {}
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
    ) -> APIOperation:
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
        operation = APIOperation.create_running(
            operation_id,
            operation_type,
            request_id=request_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )
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
        return self.get_typed(operation_id) or operation

    def submit_typed(
        self,
        operation_type: str,
        runner: Callable[[], Any],
        *,
        request_id: str | None = None,
        trace_id: str | None = None,
        client_ip: str | None = None,
    ) -> APIOperation:
        """Запускает фоновую операцию и возвращает typed snapshot."""
        return self.submit(
            operation_type,
            runner,
            request_id=request_id,
            trace_id=trace_id,
            client_ip=client_ip,
        )

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
        status: OperationStatus,
        result: Any | None = None,
        error: str | None = None,
    ) -> None:
        with self._lock:
            operation = self._operations.get(operation_id)
            if operation is None:
                return
            operation.complete(status, result=result, error=error)
            if status == "succeeded":
                self._completed_total += 1
            elif status == "failed":
                self._failed_total += 1
            done_event = self._events.get(operation_id)
            if done_event is not None:
                done_event.set()

    def get(self, operation_id: str) -> APIOperation | None:
        """Возвращает snapshot операции по id."""
        with self._lock:
            self._cleanup_expired_locked()
            operation = self._operations.get(operation_id)
            if operation is None:
                return None
            return operation

    def get_typed(self, operation_id: str) -> APIOperation | None:
        """Возвращает typed snapshot операции по id."""
        return self.get(operation_id)

    def wait(
        self,
        operation_id: str,
        timeout: float,
    ) -> APIOperation | None:
        """Ожидает завершение операции ограниченное время."""
        with self._lock:
            event = self._events.get(operation_id)
        if event is None:
            return self.get(operation_id)
        event.wait(timeout=timeout)
        return self.get(operation_id)

    def wait_typed(
        self,
        operation_id: str,
        timeout: float,
    ) -> APIOperation | None:
        """Ожидает завершение операции и возвращает typed snapshot."""
        return self.wait(operation_id, timeout)

    def _cleanup_expired_locked(self) -> None:
        now = datetime.now(UTC).timestamp()
        stale_ids: list[str] = []
        for op_id, op in self._operations.items():
            completed_at = op.completed_at
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
    ) -> APIOperation:
        operation_id = uuid.uuid4().hex
        operation = APIOperation.create_failed(
            operation_id,
            operation_type,
            error_message,
        )
        with self._lock:
            self._cleanup_expired_locked()
            self._operations[operation_id] = operation
            done_event = threading.Event()
            done_event.set()
            self._events[operation_id] = done_event
            self._rejected_total += 1
            self._failed_total += 1
        return operation

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
