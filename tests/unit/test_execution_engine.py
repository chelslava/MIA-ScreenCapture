"""Тесты execution engine для scheduler-задач."""

from datetime import datetime
from threading import Lock, Thread
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from scheduler.execution_engine import SchedulerExecutionEngine
from scheduler.task_scheduler import (
    RecordingParams,
    ScheduleTask,
    ScheduleType,
)


def _make_engine(
    tasks: dict,
    *,
    callback=None,
    save_tasks=None,
    next_run_time: datetime | None = None,
) -> SchedulerExecutionEngine:
    """Вспомогательная фабрика engine с разумными дефолтами."""
    if save_tasks is None:
        save_tasks = MagicMock()
    if callback is None:
        callback = MagicMock()
    scheduler = SimpleNamespace(
        get_job=lambda task_id: (
            SimpleNamespace(next_run_time=next_run_time)
            if next_run_time is not None
            else None
        )
    )
    return SchedulerExecutionEngine(
        lock=Lock(),
        tasks=tasks,
        scheduler=scheduler,
        save_tasks=save_tasks,
        get_on_task_execute=lambda: callback,
    )


class TestSchedulerExecutionEngine:
    """Проверки выполнения задач через выделенный execution engine."""

    # ------------------------------------------------------------------
    # базовое выполнение
    # ------------------------------------------------------------------

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

    def test_execute_increments_run_count_on_every_call(self) -> None:
        """Каждый вызов execute увеличивает run_count на 1."""
        task = ScheduleTask(
            id="task-cnt",
            name="Count task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="10:00",
        )
        tasks = {task.id: task}
        engine = _make_engine(tasks)

        engine.execute(task.id)
        engine.execute(task.id)
        engine.execute(task.id)

        assert task.run_count == 3

    def test_execute_passes_task_params_to_callback(self) -> None:
        """callback должен получать именно params конкретной задачи."""
        params = RecordingParams(area_type="window", fps=60)
        task = ScheduleTask(
            id="task-params",
            name="Params task",
            schedule_type=ScheduleType.INTERVAL,
            params=params,
            interval_minutes=10,
        )
        tasks = {task.id: task}
        callback = MagicMock()
        engine = _make_engine(tasks, callback=callback)

        engine.execute(task.id)

        callback.assert_called_once_with(params)

    def test_execute_updates_next_run_from_scheduler_job(self) -> None:
        """next_run задачи обновляется из APScheduler job при его наличии."""
        scheduled_time = datetime(2027, 6, 1, 12, 0, 0)
        task = ScheduleTask(
            id="task-nxt",
            name="Next run task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="12:00",
        )
        tasks = {task.id: task}
        engine = _make_engine(tasks, next_run_time=scheduled_time)

        engine.execute(task.id)

        assert task.next_run == scheduled_time

    def test_execute_leaves_next_run_unchanged_when_job_absent(self) -> None:
        """Если APScheduler job отсутствует, next_run не изменяется."""
        task = ScheduleTask(
            id="task-nojob",
            name="No job task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="12:00",
        )
        task.next_run = None
        tasks = {task.id: task}
        engine = _make_engine(tasks)  # next_run_time=None → job=None

        engine.execute(task.id)

        assert task.next_run is None

    def test_execute_calls_save_tasks_after_updating_metadata(self) -> None:
        """save_tasks вызывается после обновления метаданных задачи."""
        task = ScheduleTask(
            id="task-save",
            name="Save task",
            schedule_type=ScheduleType.ONCE,
            params=RecordingParams(),
            start_time=datetime.now(),
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()
        engine = _make_engine(tasks, save_tasks=save_tasks)

        engine.execute(task.id)

        save_tasks.assert_called_once()

    def test_execute_skips_callback_when_get_on_task_execute_returns_none(
        self,
    ) -> None:
        """Если callback не установлен (None), execute не падает."""
        task = ScheduleTask(
            id="task-nocb",
            name="No callback task",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="08:00",
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()
        scheduler = SimpleNamespace(get_job=lambda task_id: None)
        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks=tasks,
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: None,
        )

        engine.execute(task.id)  # не должен бросить исключение

        assert task.run_count == 1
        save_tasks.assert_called_once()

    # ------------------------------------------------------------------
    # задача не найдена
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # обработка исключений callback
    # ------------------------------------------------------------------

    def test_execute_logs_callback_error_without_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Ошибка callback (RuntimeError) не должна ломать выполнение engine."""
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

    def test_execute_logs_oserror_in_callback_without_crash(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """OSError в callback логируется и не прерывает выполнение."""
        task = ScheduleTask(
            id="task-oserr",
            name="OSError callback",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="09:00",
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()

        def os_error_callback(_params: RecordingParams) -> None:
            raise OSError("disk full")

        scheduler = SimpleNamespace(get_job=lambda task_id: None)
        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks=tasks,
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: os_error_callback,
        )

        with caplog.at_level("ERROR"):
            engine.execute(task.id)

        assert "Ошибка выполнения обратного вызова задачи" in caplog.text

    def test_execute_logs_unexpected_exception_in_callback(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Произвольное непредвиденное исключение в callback логируется через logger.exception."""
        task = ScheduleTask(
            id="task-unexpected",
            name="Unexpected error",
            schedule_type=ScheduleType.DAILY,
            params=RecordingParams(),
            time_of_day="10:00",
        )
        tasks = {task.id: task}
        save_tasks = MagicMock()

        def unexpected_callback(_params: RecordingParams) -> None:
            raise KeyError("unexpected key error")

        scheduler = SimpleNamespace(get_job=lambda task_id: None)
        engine = SchedulerExecutionEngine(
            lock=Lock(),
            tasks=tasks,
            scheduler=scheduler,
            save_tasks=save_tasks,
            get_on_task_execute=lambda: unexpected_callback,
        )

        with caplog.at_level("ERROR"):
            engine.execute(task.id)

        assert "Непредвиденная ошибка обратного вызова задачи" in caplog.text
        save_tasks.assert_called_once()

    # ------------------------------------------------------------------
    # параллельный вызов
    # ------------------------------------------------------------------

    def test_concurrent_execute_calls_are_serialized_by_lock(self) -> None:
        """Параллельные вызовы execute не должны приводить к гонке run_count."""
        task = ScheduleTask(
            id="task-concurrent",
            name="Concurrent task",
            schedule_type=ScheduleType.INTERVAL,
            params=RecordingParams(),
            interval_minutes=1,
        )
        tasks = {task.id: task}
        engine = _make_engine(tasks)

        threads = [
            Thread(target=engine.execute, args=(task.id,)) for _ in range(10)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert task.run_count == 10
