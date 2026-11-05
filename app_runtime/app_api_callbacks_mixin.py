"""API-callbacks VideoRecorderApp (#176).

Реализации колбэков для setup_api_callbacks: запись, планировщик,
устройства/мониторы/диск, webhook, verify/repair файлов и запуск
функций в GUI-потоке.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    pass
from app_runtime.app_shared_state import AppSharedState
from app_runtime.constants import (
    GUI_DEFAULT_TIMEOUT_SECONDS,
)
from config import get_config
from exceptions import (
    TaskValidationError,
)
from logger_config import get_module_logger
from recorder.utils import (
    get_audio_devices,
    get_available_monitors,
    get_available_windows,
    get_disk_space_status,
)

logger = get_module_logger(__name__)


class ApiCallbacksMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def _run_on_gui_thread(
        self,
        fn: Any,
        timeout: float | None = GUI_DEFAULT_TIMEOUT_SECONDS,
    ) -> Any:
        """Безопасный синхронный вызов функции в GUI-потоке."""
        if not self._main_window:
            return fn()
        if self._gui_thread_id == threading.get_ident():
            return fn()
        if self._gui_executor is None:
            raise RuntimeError("GUI executor не инициализирован")
        if self._command_queue is not None:
            return self._command_queue.submit_sync(
                self._gui_executor.run_sync,
                fn,
                timeout=timeout,
            )
        return self._gui_executor.run_sync(fn, timeout=timeout)

    def _get_status(self) -> dict[str, Any]:
        """Получение статуса записи."""
        return self._recording_runtime_coordinator.get_status()

    def _get_recording_metrics(self) -> dict[str, Any]:
        """Получение метрик текущей записи (#114)."""
        return self._recording_runtime_coordinator.get_metrics()

    def _start_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запуск записи."""
        return self._recording_runtime_coordinator.start_recording(params)

    def _stop_recording(self) -> dict[str, Any]:
        """Остановка записи."""
        return self._recording_runtime_coordinator.stop_recording()

    def _toggle_pause(self) -> dict[str, Any]:
        """Переключение состояния паузы."""
        return self._recording_runtime_coordinator.toggle_pause()

    def _switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """Переключение источника захвата активной записи (#48)."""
        return self._recording_runtime_coordinator.switch_capture_source(
            params
        )

    def _start_multi_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """
        Запуск мультиисточниковой записи (#51).

        Не идёт через `_recording_runtime_coordinator`/GUI — отдельный путь,
        не зависящий от single-recording стека. Но проверяет, что обычная
        запись сейчас не активна, чтобы не конкурировать за источники
        захвата/диск с уже идущей одиночной записью.
        """
        single_status = self._recording_runtime_coordinator.get_status()
        if single_status.get("is_recording") or single_status.get("is_paused"):
            return {
                "success": False,
                "error": (
                    "Обычная запись уже активна — остановите её перед "
                    "началом мультиисточниковой записи"
                ),
            }
        return self._multi_recording_service.start_multi_recording(params)

    def _stop_multi_recording(self) -> dict[str, Any]:
        """Остановка мультиисточниковой записи (#51)."""
        return self._multi_recording_service.stop_multi_recording()

    def _get_multi_recording_status(self) -> dict[str, Any]:
        """Статус мультиисточниковой записи (#51)."""
        return self._multi_recording_service.get_multi_status()

    def _get_recordings(self) -> list[Any]:
        """Получение недавних записей."""
        return self._recording_runtime_coordinator.get_recordings()

    def _get_schedule(self) -> list:
        """Получение запланированных задач."""
        if self._scheduler:
            return [task.to_dict() for task in self._scheduler.get_all_tasks()]
        return []

    def _create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создание запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            success = self._scheduler.add_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(
                        self._scheduler.get_all_tasks()
                    )
                )

            return {
                "success": success,
                "task_id": task.id if success else None,
            }
        except (TaskValidationError, ValueError, RuntimeError) as e:
            return {"success": False, "error": str(e)}

    def _delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.remove_task(task_id)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success}

    def _delete_schedules(self, task_ids: list) -> dict[str, Any]:
        """Массовое удаление запланированных задач (#160)."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        deleted = sum(
            1 for task_id in task_ids if self._scheduler.remove_task(task_id)
        )

        if deleted and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": True, "deleted": deleted}

    def _toggle_schedules(
        self, task_ids: list, enabled: bool
    ) -> dict[str, Any]:
        """Массовое включение/отключение запланированных задач (#160)."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        toggled = 0
        for task_id in task_ids:
            if self._scheduler.enable_task(task_id, enabled):
                toggled += 1

        if toggled and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": True, "toggled": toggled}

    def _update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновление запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        try:
            task = self._scheduler.create_task_from_dict(data)
            task.id = data.get("id", task.id)
            success = self._scheduler.update_task(task)

            if success and self._main_window:
                self._run_on_gui_thread(
                    lambda: self._main_window.scheduler_tab.set_tasks(
                        self._scheduler.get_all_tasks()
                    )
                )

            return {"success": success}
        except (TaskValidationError, ValueError, RuntimeError) as e:
            return {"success": False, "error": str(e)}

    def _toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """Переключение запланированной задачи."""
        if not self._scheduler:
            return {"success": False, "error": "Планировщик недоступен"}

        success = self._scheduler.enable_task(task_id, enabled)

        if success and self._main_window:
            self._run_on_gui_thread(
                lambda: self._main_window.scheduler_tab.set_tasks(
                    self._scheduler.get_all_tasks()
                )
            )

        return {"success": success, "enabled": enabled}

    def _get_devices(self) -> dict[str, list]:
        """Получение аудиоустройств."""
        return cast(dict[str, list], get_audio_devices())

    def _get_windows(self) -> list:
        """Получение доступных окон."""
        return cast(list, get_available_windows())

    def _get_monitors(self) -> list:
        """Получение доступных мониторов (#48)."""
        return cast(list, get_available_monitors())

    def _get_disk_space(self) -> dict[str, Any]:
        """Получение статуса свободного места на диске для пути записи."""
        output_path = get_config().get_output_path()
        return get_disk_space_status(output_path)

    def _get_webhook_config(self) -> dict[str, Any]:
        """Получение настроек webhook (без значения секрета)."""
        api_settings = get_config().settings.api
        return {
            "url": api_settings.webhook_url,
            "enabled": api_settings.webhook_enabled,
            "has_secret": bool(api_settings.webhook_secret),
        }
