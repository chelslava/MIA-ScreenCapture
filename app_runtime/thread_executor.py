"""Выполнение callables в главном потоке Qt."""

from __future__ import annotations

import threading
from typing import Any


class MainThreadExecutor:
    """Выполнение callables в главном потоке Qt из фоновых потоков."""

    def __init__(self) -> None:
        from PyQt6.QtCore import QObject, Qt, pyqtSignal

        class _ExecutorObject(QObject):
            execute = pyqtSignal(object)

        self._obj = _ExecutorObject()
        self._obj.execute.connect(
            self._run_callable,
            Qt.ConnectionType.QueuedConnection,
        )  # type: ignore[call-arg]

    @staticmethod
    def _run_callable(fn: Any) -> None:
        fn()

    def run_sync(self, fn: Any, timeout: float | None = 10.0) -> Any:
        """Выполнить callable в GUI-потоке и дождаться результата."""
        done = threading.Event()
        result: dict[str, Any] = {}

        def wrapped() -> None:
            try:
                result["value"] = fn()
            except Exception as e:
                result["error"] = e
            finally:
                done.set()

        self._obj.execute.emit(wrapped)
        if not done.wait(timeout):
            raise TimeoutError("Таймаут выполнения в GUI потоке")
        if "error" in result:
            raise result["error"]
        return result.get("value")
