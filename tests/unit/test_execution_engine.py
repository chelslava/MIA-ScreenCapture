"""Тесты execution engine для scheduler-задач."""

from datetime import datetime
from threading import Lock
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scheduler.execution_engine import SchedulerExecutionEngine
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)


class TestSchedulerExecutionEngine:
    """Проверки выполнения задач через выделенный execution engine."""

    def test_execute_updates_runtime_fields_and_calls_callback(self) -> None:
        """Engine должен обновлять run_count/last_run и вызвать callback."""
        task = ScheduleTask(
            id="task-1",
            name="Test task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="10:00",
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()
        callback = MagicMock()
        scheduler = SimpleNamespace(
            get_job=lambda task_id: SimpleNamespace(
                next_run_time=datetime.now()
            )
        )
        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks=tasks,
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: callback,
        )

        engine.execute(task.id)

        assert task.run_count == 1
        assert isinstance(task.last_run, datetime)
        assert isinstance(task.next_run, datetime)
        save_tasks.assert_called_once()
        callback.assert_called_once_with(task.params)

    def test_execute_returns_when_task_not_found(self) -> None:
        """Для отсутствующей задачи engine не должен падать."""
        save_tasks = MagicMock()
        callback = MagicMock()
        scheduler = SimpleNamespace(get_job=lambda task_id: None)
        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks={},
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: callback,
        )

        engine.execute("missing-task")

        save_tasks.assert_not_called()
        callback.assert_not_called()

    def test_execute_logs_callback_error_without_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ошибка callback не должна ломать выполнение engine."""
        task = ScheduleTask(
            id="task-2",
            name="Failing callback",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
            start_time=datetime.now(),
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()
        scheduler = SimpleNamespace(get_job=lambda task_id: None)

        def failing_callback(_params: RecordingParams) -> None:
            raise RuntimeError("callback failed")

        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks=tasks,
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: failing_callback,
        )

        with caplog.at_level("ERROR"):
            engine.execute(task.id)

        assert "Ошибка выполнения обратного вызова задачи" in caplog.text
        save_tasks.assert_called_once()
