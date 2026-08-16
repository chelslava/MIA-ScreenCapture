"""
Очередь команд с поддержкой backpressure и ограничением размера.
================================================================

Предоставляет потокобезопасную очередь команд для передачи вызовов
из фоновых потоков (например, API-потоков Waitress) в главный или
исполнительный поток с механизмом backpressure.

Если очередь заполнена (достигнут maxsize), новые команды отклоняются
с выбросом ``CommandQueueFullError``, что предотвращает блокировку
API-сервера и неуправляемый рост задержек.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

from exceptions import CommandQueueFullError, CommandTimeoutError
from logger_config import get_module_logger

logger = get_module_logger(__name__)

T = TypeVar("T")

_DEFAULT_QUEUE_MAXSIZE = 50
_DEFAULT_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True, slots=True)
class CommandQueueStats:
    """Метрики работы очереди команд."""

    queue_size: int
    maxsize: int
    total_submitted: int
    total_completed: int
    total_rejected: int
    total_timeouts: int


class CommandQueue:
    """Потокобезопасная очередь команд с поддержкой backpressure.

    Args:
        maxsize: Максимальное допустимое число элементов в очереди.
            При превышении вызов ``submit`` или ``submit_sync`` выбрасывает
            ``CommandQueueFullError``.
    """

    def __init__(self, maxsize: int = _DEFAULT_QUEUE_MAXSIZE) -> None:
        if maxsize < 1:
            raise ValueError(f"maxsize должен быть >= 1, получено {maxsize}")
        self._maxsize = maxsize
        self._lock = threading.Lock()
        self._pending_count = 0
        self._total_submitted = 0
        self._total_completed = 0
        self._total_rejected = 0
        self._total_timeouts = 0

    @property
    def maxsize(self) -> int:
        """Максимальная вместимость очереди."""
        return self._maxsize

    def submit_sync(
        self,
        executor: Callable[[Callable[[], T], float | None], T],
        fn: Callable[[], T],
        timeout: float | None = _DEFAULT_TIMEOUT_SECONDS,
    ) -> T:
        """Синхронно отправляет команду на исполнение через ``executor``.

        Сначала проверяется лимит вместимости очереди (backpressure).
        Если очередь не заполнена, команда передаётся в ``executor``.

        Args:
            executor: Функция исполнения (например, ``MainThreadExecutor.run_sync``).
            fn: Выполняемая функция.
            timeout: Таймаут ожидания в секундах.

        Returns:
            Результат выполнения ``fn()``.

        Raises:
            CommandQueueFullError: Если очередь заполнена (backpressure).
            CommandTimeoutError: Если превышен таймаут исполнения.
        """
        with self._lock:
            if self._pending_count >= self._maxsize:
                self._total_rejected += 1
                logger.warning(
                    "Backpressure: очередь команд заполнена (%d/%d). Запрос отклонён.",
                    self._pending_count,
                    self._maxsize,
                )
                raise CommandQueueFullError(
                    "Очередь команд заполнена",
                    details=f"Достигнут лимит {self._maxsize} команд",
                )
            self._pending_count += 1
            self._total_submitted += 1

        start_time = time.monotonic()
        try:
            result = executor(fn, timeout)
            with self._lock:
                self._total_completed += 1
            return result
        except TimeoutError as e:
            with self._lock:
                self._total_timeouts += 1
            elapsed = time.monotonic() - start_time
            logger.error(
                "Таймаут выполнения команды в очереди за %.2f c: %s",
                elapsed,
                e,
            )
            raise CommandTimeoutError(
                "Таймаут выполнения команды",
                details=str(e),
            ) from e
        finally:
            with self._lock:
                self._pending_count = max(0, self._pending_count - 1)

    def get_stats(self) -> CommandQueueStats:
        """Возвращает текущие метрики очереди команд."""
        with self._lock:
            return CommandQueueStats(
                queue_size=self._pending_count,
                maxsize=self._maxsize,
                total_submitted=self._total_submitted,
                total_completed=self._total_completed,
                total_rejected=self._total_rejected,
                total_timeouts=self._total_timeouts,
            )

    def reset_stats(self) -> None:
        """Сбрасывает счётчики статистики."""
        with self._lock:
            self._total_submitted = 0
            self._total_completed = 0
            self._total_rejected = 0
            self._total_timeouts = 0
