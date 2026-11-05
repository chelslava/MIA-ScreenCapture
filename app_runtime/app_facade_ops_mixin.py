"""Фасадные делегаты VideoRecorderApp (#176).

Однострочные обёртки над ApplicationFacade для callbacks API:
запись, планировщик, устройства, webhook, библиотека и др."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    from api.server import APIServer
    from api.websocket import WebSocketManager
from app_runtime.constants import (
    GUI_DEFAULT_TIMEOUT_SECONDS,
)
from core.application_facade import ApplicationFacade
from logger_config import get_module_logger

logger = get_module_logger(__name__)


from app_runtime.app_shared_state import AppSharedState


class FacadeOpsMixin(AppSharedState):
    """Миксин VideoRecorderApp: см. docstring модуля."""

    def get_application_facade(self) -> ApplicationFacade:
        """Возвращает concrete application facade для внешних consumers."""
        return self._application_service

    def request_start_recording(self) -> dict[str, Any]:
        """Интерактивный запуск записи из tray/hotkeys."""
        return self.start_recording()

    def get_runtime_config(self) -> dict[str, Any]:
        """Возвращает CLI/runtime конфигурацию приложения."""
        return self._config

    def get_runtime_mode(self) -> str:
        """Возвращает текущий режим запуска приложения."""
        return str(self._mode)

    def get_api_server_instance(self) -> APIServer | None:
        """Возвращает текущий runtime API server instance."""
        return self._api_server

    def set_api_server_instance(self, server: APIServer | None) -> None:
        """Устанавливает текущий runtime API server instance."""
        self._api_server = server

    def get_websocket_manager_instance(self) -> WebSocketManager:
        """Возвращает WebSocket manager приложения."""
        return self._websocket_manager

    def request_stop_recording(self) -> dict[str, Any]:
        """Интерактивный запрос остановки записи из tray/hotkeys."""
        if self._main_window:
            return cast(
                dict[str, Any],
                self._run_on_gui_thread(
                    self._main_window.request_stop_recording,
                    timeout=GUI_DEFAULT_TIMEOUT_SECONDS,
                ),
            )
        return self.stop_recording()

    def request_toggle_pause_recording(self) -> dict[str, Any]:
        """Интерактивное переключение паузы из tray/hotkeys."""
        if self._main_window:
            return cast(
                dict[str, Any],
                self._run_on_gui_thread(
                    self._main_window.request_toggle_pause,
                    timeout=GUI_DEFAULT_TIMEOUT_SECONDS,
                ),
            )
        return self.toggle_pause()

    def get_status(self) -> dict[str, Any]:
        """Возвращает публичный статус записи."""
        return self._get_status()

    def get_recording_metrics(self) -> dict[str, Any]:
        """Возвращает метрики текущей записи (#114)."""
        return self._get_recording_metrics()

    def get_finalization_status(self) -> dict[str, Any]:
        """Возвращает статус финализации записи (#151)."""
        return self._recording_runtime_coordinator.get_finalization_status()

    def start_recording(
        self,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Запускает запись через публичный фасад приложения."""
        if params is None:
            return self._recording_runtime_coordinator.start_recording()
        return self._start_recording(params)

    def stop_recording(self) -> dict[str, Any]:
        """Останавливает запись через публичный фасад приложения."""
        return self._stop_recording()

    def toggle_pause(self) -> dict[str, Any]:
        """Переключает паузу через публичный фасад приложения."""
        return self._toggle_pause()

    def switch_capture_source(self, params: dict[str, Any]) -> dict[str, Any]:
        """Переключает источник захвата через публичный фасад приложения."""
        return self._switch_capture_source(params)

    def start_multi_recording(self, params: dict[str, Any]) -> dict[str, Any]:
        """Запускает запись с нескольких источников одновременно (#51)."""
        return self._start_multi_recording(params)

    def stop_multi_recording(self) -> dict[str, Any]:
        """Останавливает мультиисточниковую запись (#51)."""
        return self._stop_multi_recording()

    def get_multi_recording_status(self) -> dict[str, Any]:
        """Возвращает статус мультиисточниковой записи (#51)."""
        return self._get_multi_recording_status()

    def get_recordings(self) -> list[Any]:
        """Возвращает список последних записей."""
        return self._get_recordings()

    def get_schedule(self) -> list[Any]:
        """Возвращает список задач планировщика."""
        return self._get_schedule()

    def create_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Создаёт задачу планировщика."""
        return self._create_schedule(data)

    def delete_schedule(self, task_id: str) -> dict[str, Any]:
        """Удаляет задачу планировщика."""
        return self._delete_schedule(task_id)

    def update_schedule(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет задачу планировщика."""
        return self._update_schedule(data)

    def toggle_schedule(
        self,
        task_id: str,
        enabled: bool,
    ) -> dict[str, Any]:
        """Переключает состояние задачи планировщика."""
        return self._toggle_schedule(task_id, enabled)

    def get_devices(self) -> dict[str, list[Any]]:
        """Возвращает список доступных аудиоустройств."""
        return self._get_devices()

    def get_windows(self) -> list[Any]:
        """Возвращает список доступных окон."""
        return self._get_windows()

    def get_monitors(self) -> list[Any]:
        """Возвращает список доступных мониторов (#48)."""
        return self._get_monitors()

    def get_disk_space(self) -> dict[str, Any]:
        """Возвращает статус свободного места на диске для пути записи."""
        return self._get_disk_space()

    def get_webhook_config(self) -> dict[str, Any]:
        """Возвращает настройки webhook (без значения секрета)."""
        return self._get_webhook_config()

    def configure_webhook(
        self, url: str | None, secret: str | None, enabled: bool
    ) -> dict[str, Any]:
        """Настраивает webhook-уведомления."""
        return self._configure_webhook(url, secret, enabled)

    def test_webhook(self) -> dict[str, Any]:
        """Отправляет тестовое webhook-уведомление."""
        return self._test_webhook()

    def verify_recording(self, file_path: str) -> dict[str, Any]:
        """Проверяет целостность видеофайла по указанному пути."""
        return self._verify_recording_file(file_path)

    def repair_recording(self, file_path: str) -> dict[str, Any]:
        """Пытается восстановить видеофайл по указанному пути."""
        return self._repair_recording_file(file_path)

    def get_config_snapshot(self) -> dict[str, Any]:
        """Возвращает snapshot текущей конфигурации."""
        return self._get_config()

    def update_config(self, data: dict[str, Any]) -> dict[str, Any]:
        """Обновляет конфигурацию через публичный фасад."""
        return self._update_config(data)

    def start_api_server(self, force: bool = False) -> dict[str, Any]:
        """Запускает API сервер через публичный фасад."""
        return self._start_api_server(force=force)

    def get_api_status(self) -> dict[str, Any]:
        """Возвращает статус API через публичный фасад."""
        return self._get_api_status()

    def apply_api_settings(self, data: dict[str, Any]) -> dict[str, Any]:
        """Применяет настройки API через публичный фасад."""
        return self._apply_api_settings(data)

    def stop_api_server(self) -> dict[str, Any]:
        """Останавливает API сервер через публичный фасад."""
        return self._stop_api_server()

    def restart_api_server(self) -> dict[str, Any]:
        """Перезапускает API сервер через публичный фасад."""
        return self._restart_api_server()

    def open_api_logs_folder(self) -> None:
        """Открывает каталог логов API через публичный фасад."""
        self._api_runtime_coordinator.open_api_logs_folder()
