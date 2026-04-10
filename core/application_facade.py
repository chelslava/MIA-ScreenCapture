"""
Явный публичный фасад приложения для GUI/runtime/API интеграций.
"""

from __future__ import annotations

from typing import Any, Protocol


class ApplicationFacade(Protocol):
    """Контракт публичных команд и запросов приложения."""

    def request_start_recording(self) -> dict[str, Any]:
        """Запускает запись с текущими GUI-настройками."""
        ...

    def request_stop_recording(self) -> dict[str, Any]:
        """Запрашивает остановку записи из интерактивного UI."""
        ...

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        """Переключает паузу записи из интерактивного UI."""
        ...

    def get_status(self) -> dict[str, Any]:
        """Возвращает статус записи."""
        ...

    def start_recording(
        self, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Запускает запись с явными параметрами."""
        ...

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись."""
        ...

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу."""
        ...

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        ...

    def get_schedule(self) -> list[Any]:
        """Возвращает список задач планировщика."""
        ...

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создаёт задачу планировщика."""
        ...

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаляет задачу планировщика."""
        ...

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет задачу планировщика."""
        ...

    def toggle_schedule(self, task_id: str, enabled: bool) -> dict[str, Any]:
        """Переключает состояние задачи планировщика."""
        ...

    def get_devices(self) -> dict[str, list[Any]]:
        """Возвращает аудиоустройства."""
        ...

    def get_windows(self) -> list[Any]:
        """Возвращает список окон."""
        ...

    def get_config_snapshot(self) -> dict[str, Any]:
        """Возвращает snapshot конфигурации."""
        ...

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет конфигурацию."""
        ...

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API."""
        ...

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API."""
        ...

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""
        ...

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""
        ...

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""
        ...

    def open_api_logs_folder(self) -> None:
        """Открывает каталог логов API."""
        ...
