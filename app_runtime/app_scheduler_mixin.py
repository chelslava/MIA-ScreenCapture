"""Планировщик VideoRecorderApp (#176).

Запуск APScheduler, выполнение запланированных задач и
обработка ошибок задач."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass
from config import get_config
from exceptions import (
    RecordingError,
)
from logger_config import get_module_logger

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class SchedulerOpsMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def _start_scheduler(self) -> None:
        """Запуск планировщика задач."""
        from scheduler.task_scheduler import TaskScheduler

        # Получение пути сохранения
        config = get_config()
        persist_path = Path(config.config_path).parent / "tasks.json"
        max_concurrent_tasks = config.settings.scheduler.max_concurrent_tasks

        self._scheduler = TaskScheduler(
            persist_path=persist_path,
            max_concurrent_tasks=max_concurrent_tasks,
            event_bus=self._recording_service.event_bus,
        )
        assert self._scheduler is not None

        # Установка обратных вызовов выполнения и ошибок задач
        self._scheduler.set_task_callback(self._execute_scheduled_task)
        self._scheduler.set_task_error_callback(self._on_scheduled_task_error)

        # Запуск планировщика
        self._scheduler.start()

        # Обновление GUI если доступно
        if self._main_window:
            self._main_window.scheduler_tab.set_tasks(
                self._scheduler.get_all_tasks()
            )

            # Подключение сигналов вкладки планировщика
            self._main_window.scheduler_tab.task_created.connect(
                self._create_schedule
            )
            self._main_window.scheduler_tab.task_updated.connect(
                self._update_schedule
            )
            self._main_window.scheduler_tab.task_deleted.connect(
                self._delete_schedule
            )
            self._main_window.scheduler_tab.task_toggled.connect(
                self._toggle_schedule
            )
            # Массовые операции multi-select (#160)
            self._main_window.scheduler_tab.tasks_deleted.connect(
                self._delete_schedules
            )
            self._main_window.scheduler_tab.tasks_toggled.connect(
                self._toggle_schedules
            )

    def _execute_scheduled_task(self, params: Any) -> None:
        """Выполнение запланированной задачи записи."""
        from scheduler.task_scheduler import RecordingParams

        if isinstance(params, RecordingParams):
            param_dict = {
                "area_type": params.area_type,
                "window_title": params.window_title,
                "rect_coords": params.rect_coords,
                "audio_type": params.audio_type,
                "output_path": params.output_path,
                "fps": params.fps,
                "codec": params.codec,
                "bitrate": params.bitrate,
                "duration": params.duration,
            }
            task_id = getattr(params, "task_id", "unknown")
        else:
            param_dict = params
            task_id = params.get("id", "unknown")

        logger.info(f"Выполнение запланированной задачи: {param_dict}")

        try:
            self.get_application_facade().start_recording(param_dict)
        except TimeoutError as e:
            logger.error(
                "Таймаут запуска записи из планировщика: task_id=%s, error=%s",
                task_id,
                e,
            )
            self._on_scheduled_task_error(
                task_id, f"Таймаут запуска записи: {e}"
            )
            raise
        except (RecordingError, OSError, ValueError, RuntimeError) as e:
            logger.error(
                "Ошибка запуска записи из планировщика: task_id=%s, error=%s",
                task_id,
                e,
            )
            self._on_scheduled_task_error(task_id, str(e))
            raise

    def _on_scheduled_task_error(self, task_id: str, error_msg: str) -> None:
        """Обработка ошибки при выполнении запланированной задачи."""
        logger.error(
            "Ошибка выполнения запланированной задачи %s: %s",
            task_id,
            error_msg,
        )
        task_name = task_id
        if self._scheduler:
            task = self._scheduler.get_task(task_id)
            if task:
                task_name = task.name

        if self._recording_service and self._recording_service.event_bus:
            from core.event_bus import RecordingEvent, RecordingEventType

            self._recording_service.event_bus.publish(
                RecordingEvent(
                    event_type=RecordingEventType.ERROR,
                    payload={
                        "type": "scheduler_task_error",
                        "task_id": task_id,
                        "task_name": task_name,
                        "error": error_msg,
                        "message": (
                            f"Задача '{task_name}' завершилась ошибкой: {error_msg}"
                        ),
                    },
                )
            )

        if self._tray_icon:
            self._tray_icon.on_error(
                f"Задача '{task_name}' завершилась ошибкой: {error_msg[:100]}"
            )

        if self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window._show_non_modal_error(
                    f"Ошибка выполнения запланированной задачи '{task_name}': {error_msg}"
                )
            )

    # Реализации обратных вызовов API
