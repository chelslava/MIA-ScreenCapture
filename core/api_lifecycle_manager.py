"""Stateful lifecycle-менеджер API runtime."""

from __future__ import annotations

import threading
from typing import Literal

ApiLifecycleState = Literal[
    "created", "starting", "running", "stopping", "stopped"
]


class ApiLifecycleManager:
    """Потокобезопасный менеджер lifecycle-состояний API runtime."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._state: ApiLifecycleState = "created"

    def get_state(self) -> ApiLifecycleState:
        """Возвращает текущее состояние lifecycle."""
        with self._lock:
            return self._state

    def set_state(self, state: ApiLifecycleState) -> None:
        """Явно устанавливает состояние lifecycle."""
        with self._lock:
            self._state = state

    def try_begin_start(self) -> bool:
        """Пытается перейти в состояние `starting`."""
        with self._lock:
            if self._state in {"starting", "stopping"}:
                return False
            self._state = "starting"
            return True

    def try_begin_stop(self) -> bool:
        """Пытается перейти в состояние `stopping`."""
        with self._lock:
            if self._state == "starting":
                return False
            self._state = "stopping"
            return True
