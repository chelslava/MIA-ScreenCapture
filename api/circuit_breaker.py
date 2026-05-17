"""Паттерн Circuit Breaker для защиты API от каскадных сбоев."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from enum import Enum
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """Выбрасывается когда Circuit Breaker находится в состоянии OPEN."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit breaker '{name}' is OPEN. Retry after {retry_after:.1f}s."
        )


class CircuitBreaker:
    """
    Потокобезопасный Circuit Breaker.

    Состояния:
    - CLOSED: нормальная работа, запросы проходят.
    - OPEN: запросы отклоняются без вызова функции.
    - HALF_OPEN: пропускает ограниченное число пробных запросов.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at: float | None = None
        self._half_open_calls = 0

    @property
    def state(self) -> str:
        return self._state.value

    @property
    def failure_count(self) -> int:
        return self._failure_count

    @property
    def success_count(self) -> int:
        return self._success_count

    def get_metrics(self) -> dict[str, Any]:
        with self._lock:
            return {
                "name": self.name,
                "state": self._state.value,
                "failure_count": self._failure_count,
                "success_count": self._success_count,
            }

    def _transition_to(self, new_state: CircuitState) -> None:
        old = self._state
        self._state = new_state
        if new_state == CircuitState.OPEN:
            self._opened_at = time.monotonic()
            self._half_open_calls = 0
            logger.warning(
                "Circuit breaker '%s': %s -> OPEN (failures=%d)",
                self.name,
                old.value.upper(),
                self._failure_count,
            )
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            logger.warning(
                "Circuit breaker '%s': OPEN -> HALF_OPEN (recovery_timeout=%.1fs elapsed)",
                self.name,
                self.recovery_timeout,
            )
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            logger.info(
                "Circuit breaker '%s': %s -> CLOSED",
                self.name,
                old.value.upper(),
            )

    def _check_recovery(self) -> None:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and time.monotonic() - self._opened_at >= self.recovery_timeout
        ):
            self._transition_to(CircuitState.HALF_OPEN)

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            self._check_recovery()

            if self._state == CircuitState.OPEN:
                elapsed = (
                    time.monotonic() - self._opened_at
                    if self._opened_at is not None
                    else 0.0
                )
                retry_after = max(0.0, self.recovery_timeout - elapsed)
                raise CircuitBreakerOpenError(self.name, retry_after)

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerOpenError(self.name, 0.0)
                self._half_open_calls += 1

        try:
            result = fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failure_count += 1
                if (
                    self._state == CircuitState.HALF_OPEN
                    or self._failure_count >= self.failure_threshold
                ):
                    self._transition_to(CircuitState.OPEN)
            raise

        with self._lock:
            self._success_count += 1
            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.CLOSED)

        return result
