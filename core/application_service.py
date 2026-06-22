"""Concrete application facade для GUI/runtime/API boundary."""

from __future__ import annotations

from typing import Any

from core.application_facade import ApplicationFacade


class ApplicationService:
    """
    Конкретная реализация application facade поверх backend приложения.

    Пока сервис остаётся тонким adapter-слоем, но даёт стабильную точку
    связывания для GUI, tray/hotkeys, scheduler и API callbacks.
    """

    def __init__(self, backend: ApplicationFacade) -> None:
        self._backend = backend

    def request_start_recording(self) -> dict[str, Any]:
        """Запускает запись с текущими GUI-настройками."""
        return self._backend.request_start_recording()

    def request_stop_recording(self) -> dict[str, Any]:
        """Запрашивает остановку записи из интерактивного UI."""
        return self._backend.request_stop_recording()

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        """Переключает паузу записи из интерактивного UI."""
        return self._backend.request_toggle_pause_recording()

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус записи."""
        return self._backend.get_status()

    def start_recording(
        self,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Запускает запись с явными параметрами."""
        return self._backend.start_recording(params)

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись."""
        return self._backend.stop_recording()

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу записи."""
        return self._backend.toggle_pause()

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        return self._backend.get_recordings()

    def get_schedule(self) -> list[Any]:
        """Возвращает список задач планировщика."""
        return self._backend.get_schedule()

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создаёт задачу планировщика."""
        return self._backend.create_schedule(data)

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаляет задачу планировщика."""
        return self._backend.delete_schedule(task_id)

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет задачу планировщика."""
        return self._backend.update_schedule(data)

    def toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """Переключает состояние задачи планировщика."""
        return self._backend.toggle_schedule(task_id, enabled)

    def get_devices(self) -> dict[str, list[Any]]:
        """Возвращает аудиоустройства."""
        return self._backend.get_devices()

    def get_windows(self) -> list[Any]:
        """Возвращает список окон."""
        return self._backend.get_windows()

    def get_disk_space(self) -> dict[str, Any]:
        """Возвращает статус свободного места на диске для пути записи."""
        return self._backend.get_disk_space()

    def get_config_snapshot(self) -> dict[str, Any]:
        """Возвращает snapshot конфигурации."""
        return self._backend.get_config_snapshot()

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет конфигурацию."""
        return self._backend.update_config(data)

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API."""
        return self._backend.get_api_status()

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API."""
        return self._backend.apply_api_settings(data)

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""
        return self._backend.start_api_server(force=force)

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""
        return self._backend.stop_api_server()

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""
        return self._backend.restart_api_server()

    def open_api_logs_folder(self) -> None:
        """Открывает каталог логов API."""
        self._backend.open_api_logs_folder()
