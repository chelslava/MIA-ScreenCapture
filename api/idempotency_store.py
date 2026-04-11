"""Хранилище результатов идемпотентных API-запросов."""

from __future__ import annotations

import threading
import time

from api.runtime_models import (
    IdempotencyBeginResult,
    IdempotencyEntry,
    IdempotencyResponse,
)

_IDEMPOTENCY_RESULT_TTL_SECONDS = 3600.0
_IDEMPOTENCY_CLEANUP_INTERVAL_SECONDS = 30.0


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
        self._entries: dict[str, IdempotencyEntry] = {}
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
    ) -> IdempotencyBeginResult:
        """Регистрирует начало операции или возвращает cached-результат."""
        now = time.monotonic()
        with self._lock:
            self._cleanup_expired_locked(now)
            entry = self._entries.get(key)
            if entry is None:
                self._entries[key] = IdempotencyEntry(
                    fingerprint=fingerprint,
                    status="running",
                    created_at_monotonic=now,
                    updated_at_monotonic=now,
                )
                return IdempotencyBeginResult(state="started")

            if entry.fingerprint != fingerprint:
                return IdempotencyBeginResult(state="conflict")

            if entry.status == "running":
                return IdempotencyBeginResult(state="in_progress")

            return IdempotencyBeginResult(
                state="replay",
                response=entry.response,
            )

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
                self._entries.pop(key, None)
                return
            entry.status = "completed"
            entry.updated_at_monotonic = now
            entry.response = IdempotencyResponse(
                status_code=status_code,
                body_bytes=body_bytes,
                mimetype=mimetype or "application/json",
            )

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
            if (now - float(entry.updated_at_monotonic)) > self._ttl_seconds
        ]
        for key in stale_keys:
            self._entries.pop(key, None)
