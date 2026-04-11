"""API runtime coordinator поверх ApiRuntimeManager."""

from __future__ import annotations

from typing import Any

from core.api_runtime_manager import ApiRuntimeManager


class ApiRuntimeCoordinator:
    """Координатор runtime-операций API сервера."""

    def __init__(self, manager: ApiRuntimeManager) -> None:
        self._manager = manager

    def sync_api_key_env(self, api_key: str | None) -> None:
        """Синхронизирует API ключ через runtime-менеджер."""
        self._manager.sync_api_key_env(api_key)

    def get_effective_api_key(self) -> str | None:
        """Возвращает актуальный API ключ."""
        return self._manager.get_effective_api_key()

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер."""
        return self._manager.start_api_server(force=force)

    def get_api_runtime_settings(self) -> dict[str, Any]:
        """Возвращает runtime-настройки API."""
        return self._manager.get_api_runtime_settings()

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API."""
        return self._manager.get_api_status()

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет API-настройки."""
        return self._manager.apply_api_settings(data)

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер."""
        return self._manager.stop_api_server()

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер."""
        return self._manager.restart_api_server()

    def open_api_logs_folder(self) -> None:
        """Открывает каталог API-логов."""
        self._manager.open_api_logs_folder()

    def setup_api_callbacks(self) -> None:
        """Регистрирует callbacks API."""
        self._manager.setup_api_callbacks()
