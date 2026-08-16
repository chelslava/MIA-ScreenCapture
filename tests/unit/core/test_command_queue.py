"""Тесты для очереди команд CommandQueue и механизма backpressure."""

from __future__ import annotations

import threading
import time
from typing import Any

import pytest

from core.command_queue import CommandQueue
from exceptions import CommandQueueFullError, CommandTimeoutError


class TestCommandQueueInit:
    """Тесты инициализации очереди команд."""

    def test_default_init(self) -> None:
        queue = CommandQueue()
        assert queue.maxsize == 50
        stats = queue.get_stats()
        assert stats.queue_size == 0
        assert stats.total_submitted == 0
        assert stats.total_completed == 0
        assert stats.total_rejected == 0
        assert stats.total_timeouts == 0

    def test_custom_maxsize(self) -> None:
        queue = CommandQueue(maxsize=10)
        assert queue.maxsize == 10

    def test_invalid_maxsize_raises(self) -> None:
        with pytest.raises(ValueError, match="maxsize"):
            CommandQueue(maxsize=0)


class TestCommandQueueSubmit:
    """Тесты отправки и выполнения команд."""

    @staticmethod
    def _mock_executor(fn: Any, timeout: float | None = None) -> Any:
        return fn()

    def test_submit_sync_success(self) -> None:
        queue = CommandQueue(maxsize=5)
        res = queue.submit_sync(self._mock_executor, lambda: "ok")
        assert res == "ok"
        stats = queue.get_stats()
        assert stats.total_submitted == 1
        assert stats.total_completed == 1
        assert stats.total_rejected == 0

    def test_submit_sync_backpressure_full_queue(self) -> None:
        """Проверка выбрасывания CommandQueueFullError при заполненной очереди."""
        queue = CommandQueue(maxsize=2)
        entered = threading.Event()
        proceed = threading.Event()

        def slow_executor(fn: Any, timeout: float | None = None) -> Any:
            entered.set()
            proceed.wait(timeout=5)
            return fn()

        results: list[Any] = []
        errors: list[Exception] = []

        def worker1() -> None:
            try:
                r = queue.submit_sync(slow_executor, lambda: "w1")
                results.append(r)
            except Exception as e:
                errors.append(e)

        def worker2() -> None:
            try:
                r = queue.submit_sync(slow_executor, lambda: "w2")
                results.append(r)
            except Exception as e:
                errors.append(e)

        t1 = threading.Thread(target=worker1)
        t2 = threading.Thread(target=worker2)
        t1.start()
        t2.start()

        # Ждём, пока два потока заполнят очередь maxsize=2
        assert entered.wait(timeout=3)
        time.sleep(0.1)

        # 3-й запрос должен отклониться из-за backpressure
        with pytest.raises(CommandQueueFullError) as exc_info:
            queue.submit_sync(self._mock_executor, lambda: "w3")

        assert "заполнена" in str(exc_info.value)
        assert queue.get_stats().total_rejected == 1

        proceed.set()
        t1.join()
        t2.join()

    def test_submit_sync_timeout(self) -> None:
        """Проверка выбрасывания CommandTimeoutError при таймауте."""
        queue = CommandQueue(maxsize=5)

        def timeout_executor(fn: Any, timeout: float | None = None) -> Any:
            raise TimeoutError("GUI thread timeout")

        with pytest.raises(CommandTimeoutError) as exc_info:
            queue.submit_sync(timeout_executor, lambda: "slow")

        assert "Таймаут" in str(exc_info.value)
        assert queue.get_stats().total_timeouts == 1


class TestCommandQueueStats:
    """Тесты статистики и сброса."""

    def test_reset_stats(self) -> None:
        queue = CommandQueue(maxsize=5)
        queue.submit_sync(lambda f, t: f(), lambda: 123)
        queue.reset_stats()
        stats = queue.get_stats()
        assert stats.total_submitted == 0
        assert stats.total_completed == 0
