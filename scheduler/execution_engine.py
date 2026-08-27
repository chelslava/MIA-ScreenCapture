"""Execution engine для выполнения задач планировщика."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from threading import Lock
from typing import Any, Protocol

from core.event_bus import EventBus, RecordingEvent, RecordingEventType
from logger_config import get_module_logger

logger = get_module_logger(__name__)


class _TaskProtocol(Protocol):
    """Минимальный контракт scheduler-задачи для execution engine."""

    id: str
    name: str
    params: Any
    last_run: datetime | None
    run_count: int
    next_run: datetime | None


class _SchedulerProtocol(Protocol):
    """Минимальный контракт APScheduler для чтения next_run."""

    def get_job(self, task_id: str) -> Any | None:
        """Возвращает APScheduler job по id."""


class SchedulerExecutionEngine:
    """Инкапсулирует логику выполнения scheduler-задач."""

    def __init__(
        self,
        *,
        lock: Lock,
        tasks: Mapping[str, _TaskProtocol],
        scheduler: _SchedulerProtocol,
        save_tasks: Callable[[], None],
        get_on_task_execute: Callable[[], Callable[[Any], None] | None],
        get_on_task_error: Callable[[], Callable[[str, str], None] | None]
        | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self._lock = lock
        self._tasks = tasks
        self._scheduler = scheduler
        self._save_tasks = save_tasks
        self._get_on_task_execute = get_on_task_execute
        self._get_on_task_error = get_on_task_error or (lambda: None)
        self._event_bus = event_bus

    def _publish_error_event(
        self, task_id: str, task_name: str, error_msg: str
    ) -> None:
        """Публикует событие ошибки задачи в EventBus."""
        if self._event_bus is None:
            return
        try:
            self._event_bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.ERROR,
                    payload={
                        "type": "scheduler_task_error",
                        "task_id": task_id,
                        "task_name": task_name,
                        "error": error_msg,
                        "message": (
                            f"Ошибка выполнения запланированной задачи "
                            f"'{task_name}': {error_msg}"
                        ),
                    },
                )
            )
        except (OSError, RuntimeError) as e:
            logger.warning(
                "Не удалось опубликовать событие ошибки задачи планировщика: %s",
                e,
            )

    def execute(self, task_id: str) -> None:
        """Выполняет задачу и обновляет её runtime-метаданные."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                logger.warning("Задача %s не найдена для выполнения", task_id)
                return

            logger.info(
                "Выполнение запланированной задачи: %s (%s)",
                task_id,
                task.name,
            )
            task.last_run = datetime.now()
            task.run_count += 1

            job = self._scheduler.get_job(task_id)
            if job:
                task.next_run = job.next_run_time

        self._save_tasks()

        callback = self._get_on_task_execute()
        if callback is None:
            return
        try:
            callback(task.params)
        except (OSError, ValueError, RuntimeError) as e:
            error_msg = f"Ошибка выполнения обратного вызова задачи: {e}"
            logger.error(error_msg)
            error_callback = self._get_on_task_error()
            if error_callback is not None:
                error_callback(task_id, error_msg)
            if self._event_bus is not None:
                self._publish_error_event(task_id, task.name, error_msg)
        except Exception as e:
            # Последний барьер: callback может быть любым внешним кодом
            error_msg = f"Непредвиденная ошибка обратного вызова задачи: {e}"
            logger.exception(error_msg)
            error_callback = self._get_on_task_error()
            if error_callback is not None:
                error_callback(task_id, error_msg)
            if self._event_bus is not None:
                self._publish_error_event(task_id, task.name, error_msg)
